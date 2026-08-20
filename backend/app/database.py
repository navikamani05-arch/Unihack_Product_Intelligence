"""Database configuration and session management."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings
import os

# Ensure data directory exists
os.makedirs(os.path.dirname(settings.database_url.replace("sqlite:///", "")), exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for FastAPI to provide database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_sqlite_columns():
    """Add newly introduced nullable columns to an existing SQLite development database."""
    if "sqlite" not in settings.database_url:
        return

    additions = {
        "product_records": {
            "description": "TEXT",
            "sku_evidence_chunk_id": "VARCHAR(128)",
            "sku_source_type": "VARCHAR(50)",
            "sku_source_identifier": "VARCHAR(500)",
            "sku_source_url": "VARCHAR(500)",
            "sku_page_number": "INTEGER",
            "sku_row_number": "INTEGER",
        },
        "product_attributes": {
            "source_type": "VARCHAR(50)",
            "source_identifier": "VARCHAR(500)",
            "source_url": "VARCHAR(500)",
            "page_number": "INTEGER",
            "row_number": "INTEGER",
            "evidence_chunk_id": "VARCHAR(128)",
        },
        "evidence_chunks": {
            "stable_chunk_id": "VARCHAR(128)",
            "job_id": "INTEGER",
            "row_number": "INTEGER",
            "source_type": "VARCHAR(50)",
            "source_identifier": "VARCHAR(500)",
            "source_url": "VARCHAR(500)",
        },
        "manufacturer_master": {
            "aliases": "JSON",
        },
        "brand_master": {
            "aliases": "JSON",
        },
        "commerce_output_fields": {
            "provenance_status": "VARCHAR(30)",
        },
        "data_conflicts": {
            "investigation_id": "INTEGER",
            "conflict_type": "VARCHAR(50)",
            "severity": "VARCHAR(20)",
            "status": "VARCHAR(50)",
            "agreement_count": "INTEGER",
            "total_sources": "INTEGER",
            "agreement_percentage": "FLOAT",
            "created_at": "DATETIME",
            "resolved_at": "DATETIME",
            "evidence_snapshot": "JSON",
            "suggested_value": "VARCHAR(255)",
            "suggestion_reason": "TEXT",
            "source_authority_summary": "JSON",
            "resolution_action": "VARCHAR(50)",
            "resolution_reason": "TEXT",
        },
    }

    inspector = inspect(engine)
    with engine.begin() as connection:
        for table_name, columns in additions.items():
            if table_name not in inspector.get_table_names():
                continue
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    connection.execute(
                        text(
                            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                        )
                    )


def init_db():
    """Initialize database tables and upgrade the local SQLite schema additively."""
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()
