"""Deterministic, source-scoped multi-source conflict detection for product investigations."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.conflict import DataConflict
from app.models.investigation import InvestigationSourceJob, ProductInvestigation
from app.schemas.investigation_schema import (
    AttributeConflictResponse,
    AttributeConflictSummaryResponse,
    ConflictDetailResponse,
    ConflictResolutionRequest,
    InvestigationConflictsResponse,
    SourceAttributeValueResponse,
)
from app.services.investigation_service import (
    IDENTITY_FIELDS,
    NOT_FOUND,
    ProductInvestigationService,
    _SourceProfile,
    _normal_key,
)
from app.services.llm_extraction_service import LLMExtractionService


IDENTIFIER_ATTRIBUTE_KEYS = {
    "sku",
    "product id",
    "model number",
    "part number",
    "catalog number",
    "mpn",
}
NUMERIC_WITH_UNIT = re.compile(
    r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([a-zA-Z%°]+)?\s*$"
)


@dataclass(frozen=True)
class _NormalizedEvidence:
    """A source value retained verbatim for display with a private comparison key."""

    value: SourceAttributeValueResponse
    comparison_key: str
    numeric_value: Optional[Decimal]
    unit: Optional[str]


class ConflictDetectionService:
    """Detect and review disagreements only among jobs attached to one investigation.

    This service deliberately never chooses or overwrites a product attribute. A source-authority
    suggestion is advisory metadata for human review and all original evidence stays visible.
    """

    @staticmethod
    def _attribute_key(attribute_name: str) -> str:
        return _normal_key(attribute_name)

    @staticmethod
    def _policy_values(setting_value: str) -> set[str]:
        return {_normal_key(value) for value in setting_value.split(",") if _normal_key(value)}

    @classmethod
    def _authority_order(cls) -> List[str]:
        configured = [value.strip() for value in settings.conflict_source_authority.split(",") if value.strip()]
        return configured or [
            "manufacturer_documentation",
            "manufacturer_website",
            "structured_catalog",
            "distributor",
            "unknown",
        ]

    @classmethod
    def _source_authority(cls, item: SourceAttributeValueResponse) -> str:
        """Classify existing source types without inventing vendor ownership metadata.

        The project does not presently store a manufacturer/distributor flag. Therefore this
        configurable baseline maps PDF documentation, website content, and structured CSV data
        into the requested hierarchy and labels all other source types unknown.
        """
        source_type = (item.source_type or "").strip().casefold()
        if source_type == "pdf":
            return "manufacturer_documentation"
        if source_type in {"website", "url"}:
            return "manufacturer_website"
        if source_type == "csv":
            return "structured_catalog"
        return "unknown"

    @classmethod
    def _authority_rank(cls, authority: Optional[str]) -> int:
        order = cls._authority_order()
        try:
            return order.index(authority or "unknown")
        except ValueError:
            return len(order)

    @classmethod
    def _comparison_key(cls, item: SourceAttributeValueResponse) -> str:
        return LLMExtractionService.normalize_value_for_comparison(item.value, item.unit)

    @classmethod
    def _numeric_unit(cls, comparison_key: str) -> Tuple[Optional[Decimal], Optional[str]]:
        match = NUMERIC_WITH_UNIT.fullmatch(comparison_key)
        if not match:
            return None, None
        try:
            numeric = Decimal(match.group(1)).normalize()
        except (InvalidOperation, ValueError):
            return None, None
        return numeric, (match.group(2) or None)

    @classmethod
    def _enrich_value(cls, item: SourceAttributeValueResponse) -> SourceAttributeValueResponse:
        normalized = cls._comparison_key(item)
        return item.model_copy(
            update={
                "normalized_value": normalized,
                "source_authority": cls._source_authority(item),
            }
        )

    @classmethod
    def _normalised_evidence(cls, item: SourceAttributeValueResponse) -> _NormalizedEvidence:
        enriched = cls._enrich_value(item)
        comparison_key = enriched.normalized_value or ""
        numeric, unit = cls._numeric_unit(comparison_key)
        return _NormalizedEvidence(enriched, comparison_key, numeric, unit)

    @classmethod
    def _identity_values(cls, profile: _SourceProfile) -> Iterable[SourceAttributeValueResponse]:
        """Expose explicit identifiers even when extraction did not persist an attribute row."""
        known = {
            (cls._attribute_key(item.attribute_name), item.evidence_chunk_id)
            for item in profile.attributes
        }
        for identity in profile.identities:
            key = cls._attribute_key(identity.field)
            if key not in IDENTIFIER_ATTRIBUTE_KEYS or identity.value == NOT_FOUND:
                continue
            if (key, identity.evidence_chunk_id) in known:
                continue
            yield SourceAttributeValueResponse(
                job_id=profile.job_id,
                source_type=identity.source_type or profile.source_type,
                attribute_name=identity.field,
                value=identity.value,
                source_identifier=identity.source_identifier,
                source_url=identity.source_url,
                page_number=identity.page_number,
                row_number=identity.row_number,
                evidence_chunk_id=identity.evidence_chunk_id,
            )

    @classmethod
    def _group_attribute_values(
        cls, profiles: Sequence[_SourceProfile]
    ) -> Tuple[Dict[str, str], Dict[str, List[SourceAttributeValueResponse]]]:
        display_names: Dict[str, str] = {}
        values: Dict[str, List[SourceAttributeValueResponse]] = defaultdict(list)
        for profile in profiles:
            seen = set()
            candidates = list(profile.attributes) + list(cls._identity_values(profile))
            for item in candidates:
                key = cls._attribute_key(item.attribute_name)
                if not key or not str(item.value).strip():
                    continue
                marker = (key, item.evidence_chunk_id, item.value, item.unit)
                if marker in seen:
                    continue
                seen.add(marker)
                display_names.setdefault(key, item.attribute_name)
                values[key].append(cls._enrich_value(item))
        return display_names, values

    @classmethod
    def _severity(cls, attribute_key: str, status: str) -> Optional[str]:
        if status == "NO_CONFLICT":
            return None
        critical = cls._policy_values(settings.conflict_critical_attributes)
        high = cls._policy_values(settings.conflict_high_attributes)
        medium = cls._policy_values(settings.conflict_medium_attributes)
        if status == "IDENTITY_CONFLICT" or attribute_key in critical:
            return "CRITICAL"
        # A source omission needs review but is not evidence that a reported technical
        # value is wrong; retain the established conservative low-severity behavior.
        if status == "MISSING_IN_SOURCE":
            return "LOW"
        if attribute_key in high:
            return "HIGH"
        if attribute_key in medium:
            return "MEDIUM"
        # Formatting-only differences are normalized out before this point; unknown content
        # disagreement remains intentionally conservative.
        return "LOW"

    @classmethod
    def _status_for_values(
        cls,
        attribute_key: str,
        source_values: Sequence[SourceAttributeValueResponse],
        total_sources: int,
        attached_job_ids: Sequence[int],
    ) -> Tuple[str, int, float, List[int]]:
        """Classify one attribute without selecting or changing a source value."""
        by_key: Dict[str, set[int]] = defaultdict(set)
        normalized = [cls._normalised_evidence(item) for item in source_values]
        jobs_with_value = set()
        for item in normalized:
            if item.comparison_key:
                by_key[item.comparison_key].add(item.value.job_id)
                jobs_with_value.add(item.value.job_id)

        missing_job_ids = [job_id for job_id in attached_job_ids if job_id not in jobs_with_value]
        agreement_count = max((len(job_ids) for job_ids in by_key.values()), default=0)
        agreement_percentage = round((agreement_count / total_sources * 100) if total_sources else 0.0, 1)

        if len(by_key) <= 1:
            status_value = "MISSING_IN_SOURCE" if missing_job_ids else "NO_CONFLICT"
            return status_value, agreement_count, agreement_percentage, missing_job_ids
        if attribute_key in IDENTIFIER_ATTRIBUTE_KEYS:
            return "IDENTITY_CONFLICT", agreement_count, agreement_percentage, missing_job_ids

        numeric_values = {item.numeric_value for item in normalized if item.numeric_value is not None}
        units = {item.unit for item in normalized if item.unit}
        if len(numeric_values) == 1 and len(units) > 1:
            return "UNIT_CONFLICT", agreement_count, agreement_percentage, missing_job_ids
        return "VALUE_CONFLICT", agreement_count, agreement_percentage, missing_job_ids

    @classmethod
    def _value_groups(
        cls, values: Sequence[SourceAttributeValueResponse]
    ) -> Dict[str, List[SourceAttributeValueResponse]]:
        groups: Dict[str, List[SourceAttributeValueResponse]] = defaultdict(list)
        for item in values:
            groups[item.normalized_value or cls._comparison_key(item)].append(item)
        return groups

    @classmethod
    def _explanation_and_suggestion(
        cls,
        attribute_name: str,
        values: Sequence[SourceAttributeValueResponse],
        total_sources: int,
        status_value: str,
        missing_job_ids: Sequence[int],
    ) -> Tuple[str, Optional[str], Optional[str]]:
        groups = cls._value_groups(values)
        rendered_groups = sorted(
            ((key, group) for key, group in groups.items()),
            key=lambda item: (-len({value.job_id for value in item[1]}), cls._authority_rank(item[1][0].source_authority), item[0]),
        )
        group_text = "; ".join(
            f"‘{group[0].value}’ is reported by {len({value.job_id for value in group})}/{total_sources} source(s)"
            for _, group in rendered_groups
        )
        if status_value == "MISSING_IN_SOURCE":
            explanation = (
                f"{attribute_name} is present in {len(values)}/{total_sources} attached source(s) and "
                f"missing from job(s) {', '.join(str(job_id) for job_id in missing_job_ids)}."
            )
        elif status_value == "IDENTITY_CONFLICT":
            explanation = f"Explicit product identifiers disagree: {group_text}."
        elif status_value == "UNIT_CONFLICT":
            explanation = f"The numeric value is the same, but the reported units disagree: {group_text}."
        else:
            explanation = f"Attached sources disagree on {attribute_name}: {group_text}."

        if not rendered_groups:
            return explanation, None, "No suggested value is available because no source asserted a value."
        winning_key, winning_group = rendered_groups[0]
        best = min(winning_group, key=lambda item: cls._authority_rank(item.source_authority))
        tied_count = len({value.job_id for value in winning_group})
        authority = best.source_authority or "unknown"
        if len(rendered_groups) == 1:
            reason = f"All reporting sources agree; the displayed value is sourced from {authority}."
        elif tied_count > 1:
            reason = (
                f"Suggested for human review because {tied_count}/{total_sources} attached sources agree, "
                f"with the strongest supporting source classified as {authority}."
            )
        else:
            reason = (
                f"Suggested for human review from the highest-ranked available source authority ({authority}); "
                "this suggestion does not resolve or overwrite conflicting evidence."
            )
        return explanation, best.value, reason

    @classmethod
    def _authority_summary(cls, values: Sequence[SourceAttributeValueResponse]) -> List[dict]:
        return [
            {
                "job_id": item.job_id,
                "source_type": item.source_type,
                "source_authority": item.source_authority or "unknown",
                "rank": cls._authority_rank(item.source_authority),
            }
            for item in values
        ]

    @classmethod
    def analyze_profiles(
        cls, investigation_id: int, profiles: Sequence[_SourceProfile]
    ) -> InvestigationConflictsResponse:
        """Analyze already-scoped profiles; this method never queries global evidence."""
        attached_job_ids = [profile.job_id for profile in profiles]
        total_sources = len(attached_job_ids)
        display_names, grouped_values = cls._group_attribute_values(profiles)
        summaries: List[AttributeConflictSummaryResponse] = []
        conflicts: List[AttributeConflictResponse] = []

        for key in sorted(grouped_values, key=str.casefold):
            values = grouped_values[key]
            status_value, agreement_count, percentage, missing_job_ids = cls._status_for_values(
                key, values, total_sources, attached_job_ids
            )
            severity = cls._severity(key, status_value)
            explanation, suggested_value, suggestion_reason = cls._explanation_and_suggestion(
                display_names[key], values, total_sources, status_value, missing_job_ids
            )
            summary = AttributeConflictSummaryResponse(
                attribute_name=display_names[key],
                status=status_value,
                severity=severity,
                agreement_count=agreement_count,
                total_sources=total_sources,
                agreement_percentage=percentage,
                missing_job_ids=missing_job_ids,
                explanation=explanation if status_value != "NO_CONFLICT" else None,
                suggested_value=suggested_value if status_value != "NO_CONFLICT" else None,
                suggestion_reason=suggestion_reason if status_value != "NO_CONFLICT" else None,
            )
            summaries.append(summary)
            if status_value != "NO_CONFLICT":
                conflicts.append(
                    AttributeConflictResponse(
                        **summary.model_dump(),
                        values=values,
                        requires_review=True,
                    )
                )

        return InvestigationConflictsResponse(
            investigation_id=investigation_id,
            total_sources=total_sources,
            conflict_count=len(conflicts),
            conflicts=conflicts,
            attribute_summaries=summaries,
        )

    @classmethod
    def _conflict_key(cls, conflict: AttributeConflictResponse) -> Tuple[str, str]:
        return cls._attribute_key(conflict.attribute_name), conflict.status

    @classmethod
    def _persist_conflicts(
        cls,
        db: Session,
        investigation: ProductInvestigation,
        profiles: Sequence[_SourceProfile],
        report: InvestigationConflictsResponse,
    ) -> None:
        """Upsert summaries so a re-scan never erases an existing human review decision."""
        existing = (
            db.query(DataConflict)
            .filter(DataConflict.investigation_id == investigation.id)
            .order_by(DataConflict.id)
            .all()
        )
        existing_by_key = {
            (_normal_key(item.attribute_name), item.conflict_type or ""): item for item in existing
        }
        current_keys: set[Tuple[str, str]] = set()
        product_id = next((product_id for profile in profiles for product_id in profile.product_ids), None)

        for conflict in report.conflicts:
            if not conflict.values:
                continue
            key = cls._conflict_key(conflict)
            current_keys.add(key)
            source_a = conflict.values[0]
            source_b = next(
                (value for value in conflict.values[1:] if value.value != source_a.value),
                source_a,
            )
            snapshot = [value.model_dump(mode="json") for value in conflict.values]
            authority_summary = cls._authority_summary(conflict.values)
            entity = existing_by_key.get(key)
            if entity is None:
                entity = DataConflict(
                    product_id=product_id,
                    investigation_id=investigation.id,
                    attribute_name=conflict.attribute_name,
                    conflict_type=conflict.status,
                    source_a_name=source_a.source_identifier or source_a.source_url or source_a.source_type,
                    source_a_value=source_a.value,
                    source_b_name=source_b.source_identifier or source_b.source_url or source_b.source_type,
                    source_b_value=source_b.value,
                    resolution_status="unresolved",
                    status="REQUIRES_REVIEW",
                )
                db.add(entity)
            else:
                entity.product_id = entity.product_id or product_id
                entity.source_a_name = source_a.source_identifier or source_a.source_url or source_a.source_type
                entity.source_a_value = source_a.value
                entity.source_b_name = source_b.source_identifier or source_b.source_url or source_b.source_type
                entity.source_b_value = source_b.value
            entity.severity = conflict.severity
            entity.agreement_count = conflict.agreement_count
            entity.total_sources = conflict.total_sources
            entity.agreement_percentage = conflict.agreement_percentage
            entity.evidence_snapshot = snapshot
            entity.suggested_value = conflict.suggested_value
            entity.suggestion_reason = conflict.suggestion_reason
            entity.source_authority_summary = authority_summary
            db.flush()
            conflict.conflict_id = entity.id
            conflict.resolution_status = entity.resolution_status or "unresolved"
            conflict.resolution_action = entity.resolution_action
            conflict.resolution_reason = entity.resolution_reason

        # Remove stale, still-unresolved scan results. A resolved/human-review audit record is
        # deliberately retained even if a later scan no longer reproduces the conflict.
        for entity in existing:
            key = (_normal_key(entity.attribute_name), entity.conflict_type or "")
            if key not in current_keys and entity.resolution_status == "unresolved":
                db.delete(entity)
        db.commit()

    @classmethod
    def detect_for_investigation(
        cls, db: Session, investigation_id: int
    ) -> InvestigationConflictsResponse:
        investigation = ProductInvestigationService.get_or_raise(db, investigation_id)
        attachments = (
            db.query(InvestigationSourceJob)
            .filter(InvestigationSourceJob.investigation_id == investigation.id)
            .order_by(InvestigationSourceJob.created_at)
            .all()
        )
        profiles = [ProductInvestigationService._profile_for_job(db, attachment.job) for attachment in attachments]
        report = cls.analyze_profiles(investigation.id, profiles)
        cls._persist_conflicts(db, investigation, profiles, report)
        return report

    @classmethod
    def _entity_or_404(cls, db: Session, investigation_id: int, conflict_id: int) -> DataConflict:
        ProductInvestigationService.get_or_raise(db, investigation_id)
        entity = (
            db.query(DataConflict)
            .filter(
                DataConflict.id == conflict_id,
                DataConflict.investigation_id == investigation_id,
            )
            .first()
        )
        if entity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conflict was not found in this investigation.")
        return entity

    @classmethod
    def detail_for_conflict(cls, db: Session, investigation_id: int, conflict_id: int) -> ConflictDetailResponse:
        entity = cls._entity_or_404(db, investigation_id, conflict_id)
        values = [SourceAttributeValueResponse.model_validate(item) for item in (entity.evidence_snapshot or [])]
        return ConflictDetailResponse(
            conflict_id=entity.id,
            attribute_name=entity.attribute_name,
            status=entity.conflict_type or "VALUE_CONFLICT",
            severity=entity.severity,
            agreement_count=entity.agreement_count or 0,
            total_sources=entity.total_sources or 0,
            agreement_percentage=entity.agreement_percentage or 0.0,
            values=values,
            requires_review=entity.resolution_status in {None, "unresolved", "human_review"},
            resolution_status=entity.resolution_status or "unresolved",
            resolution_action=entity.resolution_action,
            resolution_reason=entity.resolution_reason,
            suggested_value=entity.suggested_value,
            suggestion_reason=entity.suggestion_reason,
            source_authority_summary=entity.source_authority_summary or [],
            created_at=entity.created_at.isoformat() if entity.created_at else None,
            resolved_at=entity.resolved_at.isoformat() if entity.resolved_at else None,
        )

    @classmethod
    def resolve_conflict(
        cls,
        db: Session,
        investigation_id: int,
        conflict_id: int,
        request: ConflictResolutionRequest,
    ) -> ConflictDetailResponse:
        """Store a human decision only; extracted values and source evidence are immutable."""
        entity = cls._entity_or_404(db, investigation_id, conflict_id)
        values = entity.evidence_snapshot or []
        supported_values = {str(value.get("value", "")) for value in values if value.get("value") is not None}
        action = request.action
        if action == "ACCEPT_SOURCE_VALUE":
            chosen = request.chosen_value or entity.source_a_value
            if chosen != entity.source_a_value:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="ACCEPT_SOURCE_VALUE must select the recorded source value.",
                )
            entity.resolution_status = "resolved_source_value"
            entity.status = "RESOLVED"
            entity.resolved_value = chosen
        elif action == "ACCEPT_OTHER_VALUE":
            chosen = request.chosen_value
            if not chosen or chosen not in supported_values:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="ACCEPT_OTHER_VALUE requires a value present in this conflict's source evidence.",
                )
            entity.resolution_status = "resolved_other_value"
            entity.status = "RESOLVED"
            entity.resolved_value = chosen
        elif action == "MARK_AS_HUMAN_REVIEW":
            entity.resolution_status = "human_review"
            entity.status = "HUMAN_REVIEW"
            entity.resolved_value = None
        else:  # MARK_AS_UNRESOLVED
            entity.resolution_status = "unresolved"
            entity.status = "REQUIRES_REVIEW"
            entity.resolved_value = None
        entity.resolution_action = action
        entity.resolution_reason = request.reasoning
        entity.resolved_at = datetime.utcnow() if action in {"ACCEPT_SOURCE_VALUE", "ACCEPT_OTHER_VALUE"} else None
        db.commit()
        db.refresh(entity)
        return cls.detail_for_conflict(db, investigation_id, entity.id)


__all__ = ["ConflictDetectionService"]
