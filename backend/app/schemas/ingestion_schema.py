"""Pydantic schemas for ingestion-related API requests and responses."""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class IngestionJobResponse(BaseModel):
    """Response model for an ingestion job."""
    id: int
    job_name: str
    status: str
    source_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RawDocumentSourceResponse(BaseModel):
    """Response model for a raw document source."""
    id: int
    job_id: int
    file_name: str
    file_path: Optional[str]
    source_url: Optional[str]
    parsed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class EvidenceChunkResponse(BaseModel):
    """Response model for an evidence chunk."""
    id: int
    attribute_id: Optional[int]
    source_id: int
    snippet_text: str
    page_number: Optional[int]

    model_config = {"from_attributes": True}


class PDFUploadResponse(BaseModel):
    """Response model for PDF upload."""
    job_id: int
    filename: str
    status: str
    message: str
    total_pages: Optional[int] = None
    chunks_created: Optional[int] = None


class IngestionJobDetailsResponse(BaseModel):
    """Response model for ingestion job details."""
    job_id: int
    job_name: str
    status: str
    source_type: str
    created_at: str
    source_count: int
    total_chunks: int
    sources: List[dict] = []


class IngestionStatusResponse(BaseModel):
    """Response model for ingestion status."""
    job_id: int
    status: str
    message: str
    progress: Optional[float] = None
