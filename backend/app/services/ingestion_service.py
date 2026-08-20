"""Ingestion service for managing PDF uploads and document processing."""
import hashlib
import os
import shutil
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.ingestion import IngestionJob, RawDocumentSource
from app.models.conflict import EvidenceChunk
from app.models.product import ProductAttribute
from app.services.pdf_extractor import PDFExtractor, PDFExtractionError
from app.services.website_extractor import WebsiteExtractor, WebsiteExtractionError
from app.services.csv_extractor import CSVExtractor, CSVExtractionError
from app.utils.logger import logger


class IngestionService:
    """Service for managing document ingestion and processing."""

    UPLOAD_DIR = "data/uploads"

    @staticmethod
    def _stable_chunk_id(source_type: str, source_identifier: str, position: int, text: str) -> str:
        """Create a deterministic evidence identifier from source and content."""
        value = f"{source_type}:{source_identifier}:{position}:{text}"
        return f"{source_type}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:32]}"

    @classmethod
    def ensure_upload_dir(cls):
        """Ensure upload directory exists."""
        os.makedirs(cls.UPLOAD_DIR, exist_ok=True)

    @classmethod
    def create_ingestion_job(
        cls, db: Session, job_name: str, source_type: str
    ) -> IngestionJob:
        """
        Create a new ingestion job.
        
        Args:
            db: Database session
            job_name: Name of the ingestion job
            source_type: Type of source (pdf, url, csv)
            
        Returns:
            Created IngestionJob instance
        """
        job = IngestionJob(
            job_name=job_name,
            status="pending",
            source_type=source_type,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        logger.info(f"Created ingestion job: {job.id} - {job_name}")
        return job

    @classmethod
    def save_uploaded_file(cls, file_content: bytes, filename: str) -> str:
        """
        Save uploaded file to disk.
        
        Args:
            file_content: File content as bytes
            filename: Original filename
            
        Returns:
            Path to saved file
        """
        cls.ensure_upload_dir()
        file_path = os.path.join(cls.UPLOAD_DIR, filename)
        
        # Ensure unique filename if file exists
        if os.path.exists(file_path):
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(file_path):
                file_path = os.path.join(cls.UPLOAD_DIR, f"{base}_{counter}{ext}")
                counter += 1

        with open(file_path, "wb") as f:
            f.write(file_content)

        logger.info(f"Saved file: {file_path}")
        return file_path

    @classmethod
    def process_pdf_file(
        cls, db: Session, job_id: int, file_path: str, filename: str
    ) -> Optional[RawDocumentSource]:
        """
        Process a PDF file and extract text.
        
        Args:
            db: Database session
            job_id: Ingestion job ID
            file_path: Path to the PDF file
            filename: Original filename
            
        Returns:
            RawDocumentSource instance or None if processing failed
        """
        try:
            # Validate PDF
            if not PDFExtractor.validate_pdf(file_path):
                logger.error(f"Invalid PDF file: {filename}")
                return None

            # Extract text from PDF
            extraction_result = PDFExtractor.extract_text_from_pdf(file_path)

            if extraction_result["error"]:
                logger.error(f"PDF extraction error for {filename}: {extraction_result['error']}")
                return None

            # Create RawDocumentSource record
            raw_source = RawDocumentSource(
                job_id=job_id,
                file_name=filename,
                file_path=file_path,
                raw_text_content="\n".join(
                    [p["text"] for p in extraction_result["pages"]]
                ),
                parsed_at=datetime.utcnow(),
            )
            db.add(raw_source)
            db.commit()
            db.refresh(raw_source)

            logger.info(f"Created RawDocumentSource: {raw_source.id} for {filename}")

            # Create EvidenceChunk records for each page
            for page_data in extraction_result["pages"]:
                evidence_chunk = EvidenceChunk(
                    attribute_id=None,  # Will be linked later during extraction
                    source_id=raw_source.id,
                    job_id=job_id,
                    stable_chunk_id=cls._stable_chunk_id(
                        "pdf", filename, page_data["page_number"], page_data["text"]
                    ),
                    snippet_text=page_data["text"],
                    page_number=page_data["page_number"],
                    source_type="pdf",
                    source_identifier=filename,
                    bounding_box=None,  # Can be added later if needed
                )
                db.add(evidence_chunk)

            db.commit()
            logger.info(
                f"Created {len(extraction_result['pages'])} evidence chunks for {filename}"
            )

            return raw_source

        except PDFExtractionError as e:
            logger.error(f"PDF extraction error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing PDF: {str(e)}")
            return None

    @classmethod
    def update_job_status(
        cls, db: Session, job_id: int, status: str
    ) -> IngestionJob:
        """
        Update ingestion job status.
        
        Args:
            db: Database session
            job_id: Job ID
            status: New status (pending, processing, completed, failed)
            
        Returns:
            Updated IngestionJob instance
        """
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            job.status = status
            db.commit()
            db.refresh(job)
            logger.info(f"Updated job {job_id} status to {status}")
        return job

    @classmethod
    def get_job_details(cls, db: Session, job_id: int) -> dict:
        """
        Get detailed information about an ingestion job.
        
        Args:
            db: Database session
            job_id: Job ID
            
        Returns:
            Dictionary with job details
        """
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if not job:
            return {"error": "Job not found"}

        sources = db.query(RawDocumentSource).filter(
            RawDocumentSource.job_id == job_id
        ).all()

        total_chunks = 0
        for source in sources:
            chunks = db.query(EvidenceChunk).filter(
                EvidenceChunk.source_id == source.id
            ).count()
            total_chunks += chunks

        return {
            "job_id": job.id,
            "job_name": job.job_name,
            "status": job.status,
            "source_type": job.source_type,
            "created_at": job.created_at.isoformat(),
            "source_count": len(sources),
            "total_chunks": total_chunks,
            "sources": [
                {
                    "id": s.id,
                    "filename": s.file_name,
                    "source_url": s.source_url,
                    "parsed_at": s.parsed_at.isoformat() if s.parsed_at else None,
                }
                for s in sources
            ],
        }

    @classmethod
    def process_website(cls, db: Session, job_id: int, url: str) -> Optional[RawDocumentSource]:
        """
        Process a website URL and extract content.
        
        Args:
            db: Database session
            job_id: Ingestion job ID
            url: Website URL
            
        Returns:
            RawDocumentSource instance or None if processing failed
        """
        try:
            # Extract website content
            extraction_result = WebsiteExtractor.extract_website_data(url)

            if extraction_result.get("error"):
                logger.error(f"Website extraction error for {url}: {extraction_result['error']}")
                return None

            # Create RawDocumentSource record
            raw_source = RawDocumentSource(
                job_id=job_id,
                file_name=extraction_result.get("title", url),
                source_url=url,
                raw_text_content=extraction_result.get("text", ""),
                parsed_at=datetime.utcnow(),
            )
            db.add(raw_source)
            db.commit()
            db.refresh(raw_source)

            logger.info(f"Created RawDocumentSource: {raw_source.id} for {url}")

            # Create EvidenceChunk records for each chunk
            for chunk_idx, chunk_text in enumerate(extraction_result.get("chunks", []), start=1):
                evidence_chunk = EvidenceChunk(
                    attribute_id=None,
                    source_id=raw_source.id,
                    job_id=job_id,
                    stable_chunk_id=WebsiteExtractor.generate_chunk_id(url, chunk_idx, chunk_text),
                    snippet_text=chunk_text,
                    page_number=chunk_idx,
                    source_type="website",
                    source_identifier=url,
                    source_url=url,
                    bounding_box=None,
                )
                db.add(evidence_chunk)

            db.commit()
            logger.info(
                f"Created {len(extraction_result.get('chunks', []))} evidence chunks for {url}"
            )

            return raw_source

        except WebsiteExtractionError as e:
            logger.error(f"Website extraction error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing website: {str(e)}")
            return None

    @classmethod
    def process_csv_file(cls, db: Session, job_id: int, file_path: str, filename: str) -> Optional[RawDocumentSource]:
        """
        Process a CSV file and extract data.
        
        Args:
            db: Database session
            job_id: Ingestion job ID
            file_path: Path to the CSV file
            filename: Original filename
            
        Returns:
            RawDocumentSource instance or None if processing failed
        """
        try:
            # Read CSV file
            with open(file_path, "rb") as f:
                content = f.read()

            # Validate CSV
            if not CSVExtractor.validate_csv(content):
                logger.error(f"Invalid CSV file: {filename}")
                return None

            # Extract CSV data
            extraction_result = CSVExtractor.extract_csv_data(content, filename)

            if extraction_result.get("error"):
                logger.error(f"CSV extraction error for {filename}: {extraction_result['error']}")
                return None

            # Create RawDocumentSource record
            raw_source = RawDocumentSource(
                job_id=job_id,
                file_name=filename,
                file_path=file_path,
                raw_text_content="CSV Data",
                parsed_at=datetime.utcnow(),
            )
            db.add(raw_source)
            db.commit()
            db.refresh(raw_source)

            logger.info(f"Created RawDocumentSource: {raw_source.id} for {filename}")

            # Create EvidenceChunk records for each CSV row
            columns = extraction_result.get("columns", [])
            for row_data in extraction_result.get("rows", []):
                row_number = row_data["row_number"]
                values = row_data["values"]
                
                # Convert row to text format
                row_text = CSVExtractor.row_to_text(values, columns)
                
                evidence_chunk = EvidenceChunk(
                    attribute_id=None,
                    source_id=raw_source.id,
                    job_id=job_id,
                    stable_chunk_id=row_data.get(
                        "chunk_id",
                        cls._stable_chunk_id("csv", filename, row_number, row_text),
                    ),
                    snippet_text=row_text,
                    page_number=row_number,  # Backward-compatible legacy field.
                    row_number=row_number,
                    source_type="csv",
                    source_identifier=filename,
                    bounding_box=None,
                )
                db.add(evidence_chunk)

            db.commit()
            logger.info(
                f"Created {len(extraction_result.get('rows', []))} evidence chunks for {filename}"
            )

            return raw_source

        except CSVExtractionError as e:
            logger.error(f"CSV extraction error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing CSV: {str(e)}")
            return None

    @classmethod
    def cleanup_file(cls, file_path: str) -> bool:
        """
        Delete a file from disk.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {str(e)}")
            return False
