"""Run the Phase 4 rule-quality evaluator against the configured project dataset."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db
from app.services.evaluation_service import EvaluationService


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        EvaluationService.run_rule_quality(db)
        summary = EvaluationService.latest_summary(db)
        print(json.dumps(summary.model_dump(mode="json"), indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    main()
