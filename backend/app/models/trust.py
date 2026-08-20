"""Trust metric SQLAlchemy model."""
from sqlalchemy import Column, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class TrustMetric(Base):
    """Stores multi-dimensional trust scores, completeness percentages, and ML readiness predictions."""
    __tablename__ = "trust_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("product_records.id"))
    trust_score = Column(Float, default=0.0)  # 0.0 to 100.0
    completeness_percentage = Column(Float, default=0.0)
    conflict_count = Column(Integer, default=0)
    provenance_score = Column(Float, default=0.0)
    ml_readiness_probability = Column(Float, default=0.0)
    
    product = relationship("ProductRecord", back_populates="trust_metric")
