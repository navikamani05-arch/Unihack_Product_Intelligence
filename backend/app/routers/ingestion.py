"""Ingestion API router for PDF uploads and document processing."""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.services.ingestion_service import IngestionService
from app.utils.upload import read_upload_limited, safe_upload_filename
from app.services.pdf_extractor import PDFExtractionError
from app.schemas.ingestion_schema import (
    PDFUploadResponse,
    IngestionJobDetailsResponse,
    IngestionStatusResponse,
)
from app.utils.logger import logger

router = APIRouter(prefix="/api/v1/ingest", tags=["Ingestion"])


@router.post("/upload-pdf", response_model=PDFUploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    job_name: str = "PDF Upload",
    db: Session = Depends(get_db),
):
    """
    Upload and process a PDF file.
    
    Args:
        file: PDF file to upload
        job_name: Name for the ingestion job
        db: Database session
        
    Returns:
        PDFUploadResponse with job details
    """
    try:
        # Validate file type and normalize the client-supplied filename.
        filename = safe_upload_filename(file.filename, "upload.pdf")
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are supported",
            )

        # Read file content
        content = await read_upload_limited(file)
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty",
            )

        # Create ingestion job
        job = IngestionService.create_ingestion_job(db, job_name, "pdf")

        # Save file to disk
        file_path = IngestionService.save_uploaded_file(content, filename)

        # Process PDF
        IngestionService.update_job_status(db, job.id, "processing")
        
        raw_source = IngestionService.process_pdf_file(
            db, job.id, file_path, filename
        )

        if not raw_source:
            IngestionService.update_job_status(db, job.id, "failed")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to process PDF file",
            )

        # Get chunk count
        from app.models.conflict import EvidenceChunk
        chunk_count = db.query(EvidenceChunk).filter(
            EvidenceChunk.source_id == raw_source.id
        ).count()

        IngestionService.update_job_status(db, job.id, "completed")

        logger.info("PDF upload completed: %s (Job ID: %s)", filename, job.id)

        return PDFUploadResponse(
            job_id=job.id,
            filename=filename,
            status="completed",
            message="PDF processed successfully",
            total_pages=chunk_count,
            chunks_created=chunk_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF upload error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )


@router.get("/jobs/{job_id}", response_model=IngestionJobDetailsResponse)
async def get_job_details(
    job_id: int,
    db: Session = Depends(get_db),
):
    """
    Get details about an ingestion job.
    
    Args:
        job_id: ID of the ingestion job
        db: Database session
        
    Returns:
        IngestionJobDetailsResponse with job details
    """
    try:
        details = IngestionService.get_job_details(db, job_id)
        
        if "error" in details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=details["error"],
            )

        return IngestionJobDetailsResponse(**details)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching job details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch job details",
        )


@router.get("/jobs/{job_id}/status", response_model=IngestionStatusResponse)
async def get_job_status(
    job_id: int,
    db: Session = Depends(get_db),
):
    """
    Get the status of an ingestion job.
    
    Args:
        job_id: ID of the ingestion job
        db: Database session
        
    Returns:
        IngestionStatusResponse with job status
    """
    try:
        from app.models.ingestion import IngestionJob
        
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )

        status_messages = {
            "pending": "Job is pending",
            "processing": "Job is being processed",
            "completed": "Job completed successfully",
            "failed": "Job failed",
        }

        return IngestionStatusResponse(
            job_id=job.id,
            status=job.status,
            message=status_messages.get(job.status, "Unknown status"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching job status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch job status",
        )
