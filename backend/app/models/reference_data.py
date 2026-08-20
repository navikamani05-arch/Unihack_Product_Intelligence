"""Additive ORM models for official Unilog reference data and explainable decisions."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class ReferenceDataset(Base):
    __tablename__ = "reference_datasets"

    id = Column(Integer, primary_key=True, index=True)
    dataset_type = Column(String(64), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    file_name = Column(String(500), nullable=True)
    version = Column(String(100), nullable=True)
    file_path = Column(String(1000), nullable=True)
    checksum = Column(String(64), nullable=True, index=True)
    row_count = Column(Integer, nullable=True)
    status = Column(String(40), nullable=False, default="not_available", index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    sheet_names = Column(JSON, nullable=True)
    import_statistics = Column(JSON, nullable=True)
    imported_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ManufacturerMaster(Base):
    __tablename__ = "manufacturer_master"
    __table_args__ = (UniqueConstraint("dataset_id", "comparison_value", name="uq_master_manufacturer_dataset_value"),)

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("reference_datasets.id"), nullable=False, index=True)
    display_value = Column(String(500), nullable=False)
    comparison_value = Column(String(500), nullable=False, index=True)
    manufacturer_code = Column(String(100), nullable=True, index=True)
    aliases = Column(JSON, nullable=True)
    dataset = relationship("ReferenceDataset")


class BrandMaster(Base):
    __tablename__ = "brand_master"
    __table_args__ = (UniqueConstraint("dataset_id", "manufacturer_code", "comparison_value", name="uq_master_brand_dataset_pair"),)

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("reference_datasets.id"), nullable=False, index=True)
    manufacturer_master_id = Column(Integer, ForeignKey("manufacturer_master.id"), nullable=True, index=True)
    manufacturer_code = Column(String(100), nullable=True, index=True)
    display_value = Column(String(500), nullable=False)
    comparison_value = Column(String(500), nullable=False, index=True)
    brand_code = Column(String(100), nullable=True, index=True)
    aliases = Column(JSON, nullable=True)
    dataset = relationship("ReferenceDataset")
    manufacturer = relationship("ManufacturerMaster")


class LOVEntry(Base):
    __tablename__ = "lov_entries"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("reference_datasets.id"), nullable=False, index=True)
    classpath = Column(String(1000), nullable=True, index=True)
    classpath_comparison = Column(String(1000), nullable=True, index=True)
    leaf_node = Column(String(500), nullable=True, index=True)
    attribute_label = Column(String(500), nullable=False)
    attribute_comparison = Column(String(500), nullable=False, index=True)
    attribute_values = Column(Text, nullable=True)
    normalized_label = Column(String(500), nullable=True)
    normalized_values = Column(Text, nullable=True)
    filtering_flag = Column(String(50), nullable=True)
    guidelines = Column(Text, nullable=True)
    remarks = Column(Text, nullable=True)
    dataset = relationship("ReferenceDataset")


class UOMEntry(Base):
    __tablename__ = "uom_entries"
    __table_args__ = (UniqueConstraint("dataset_id", "comparison_value", name="uq_uom_dataset_value"),)

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("reference_datasets.id"), nullable=False, index=True)
    display_value = Column(String(255), nullable=False)
    comparison_value = Column(String(255), nullable=False, index=True)
    terms = Column(JSON, nullable=True)
    dataset = relationship("ReferenceDataset")


class FractionConversion(Base):
    __tablename__ = "fraction_conversions"
    __table_args__ = (UniqueConstraint("dataset_id", "comparison_value", name="uq_fraction_dataset_value"),)

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("reference_datasets.id"), nullable=False, index=True)
    original_value = Column(String(100), nullable=False)
    comparison_value = Column(String(100), nullable=False, index=True)
    fraction_value = Column(String(100), nullable=False)
    dataset = relationship("ReferenceDataset")


class ProductNormalizationDecision(Base):
    __tablename__ = "product_normalization_decisions"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("product_records.id"), nullable=True, index=True)
    attribute_id = Column(Integer, ForeignKey("product_attributes.id"), nullable=True, index=True)
    reference_dataset_id = Column(Integer, ForeignKey("reference_datasets.id"), nullable=True, index=True)
    decision_type = Column(String(64), nullable=False, index=True)
    original_value = Column(String(1000), nullable=True)
    canonical_value = Column(String(1000), nullable=True)
    status = Column(String(64), nullable=False, index=True)
    match_type = Column(String(64), nullable=True)
    confidence = Column(Float, nullable=True)
    explanation = Column(Text, nullable=False)
    provenance_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    dataset = relationship("ReferenceDataset")
