"""Multi-source ingestion API router for Website and CSV uploads."""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.ingestion_service import IngestionService
from app.services.website_extractor import WebsiteExtractionError
from app.services.csv_extractor import CSVExtractionError
from app.schemas.ingestion_schema import PDFUploadResponse
from app.utils.logger import logger
from app.utils.upload import read_upload_limited, safe_upload_filename

router = APIRouter(prefix="/api/v1/ingest", tags=["Ingestion"])


@router.post("/upload-website", response_model=PDFUploadResponse)
async def upload_website(
    url: str = Query(..., description="Website URL to scrape"),
    job_name: str = Query("Website Upload", description="Name for the ingestion job"),
    db: Session = Depends(get_db),
):
    """
    Upload and process a website URL.
    
    Args:
        url: Website URL to extract product data from
        job_name: Name for the ingestion job
        db: Database session
        
    Returns:
        PDFUploadResponse with job details
    """
    try:
        # Validate URL
        if not url.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL must start with http:// or https://",
            )

        # Create ingestion job
        job = IngestionService.create_ingestion_job(db, job_name, "url")

        # Process website
        IngestionService.update_job_status(db, job.id, "processing")
        
        raw_source = IngestionService.process_website(db, job.id, url)

        if not raw_source:
            IngestionService.update_job_status(db, job.id, "failed")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to process website",
            )

        # Get chunk count
        from app.models.conflict import EvidenceChunk
        chunk_count = db.query(EvidenceChunk).filter(
            EvidenceChunk.source_id == raw_source.id
        ).count()

        IngestionService.update_job_status(db, job.id, "completed")

        logger.info(f"Website ingestion completed: {url} (Job ID: {job.id})")

        return PDFUploadResponse(
            job_id=job.id,
            filename=url,
            status="completed",
            message="Website processed successfully",
            total_pages=chunk_count,
            chunks_created=chunk_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Website ingestion error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}",
        )


@router.post("/upload-csv", response_model=PDFUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    job_name: str = Query("CSV Upload", description="Name for the ingestion job"),
    db: Session = Depends(get_db),
):
    """
    Upload and process a CSV file.
    
    Args:
        file: CSV file to upload
        job_name: Name for the ingestion job
        db: Database session
        
    Returns:
        PDFUploadResponse with job details
    """
    try:
        # Validate file type and normalize the client-supplied filename.
        filename = safe_upload_filename(file.filename, "upload.csv")
        if not filename.lower().endswith(".csv"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only CSV files are supported",
            )

        # Read file content
        content = await read_upload_limited(file)
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty",
            )

        # Create ingestion job
        job = IngestionService.create_ingestion_job(db, job_name, "csv")

        # Save file to disk
        file_path = IngestionService.save_uploaded_file(content, filename)

        # Process CSV
        IngestionService.update_job_status(db, job.id, "processing")
        
        raw_source = IngestionService.process_csv_file(
            db, job.id, file_path, filename
        )

        if not raw_source:
            IngestionService.update_job_status(db, job.id, "failed")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to process CSV file",
            )

        # Get chunk count
        from app.models.conflict import EvidenceChunk
        chunk_count = db.query(EvidenceChunk).filter(
            EvidenceChunk.source_id == raw_source.id
        ).count()

        IngestionService.update_job_status(db, job.id, "completed")

        logger.info("CSV ingestion completed: %s (Job ID: %s)", filename, job.id)

        return PDFUploadResponse(
            job_id=job.id,
            filename=filename,
            status="completed",
            message="CSV processed successfully",
            total_pages=chunk_count,
            chunks_created=chunk_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV ingestion error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )
