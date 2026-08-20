"""PDF extraction service using PyMuPDF."""
import fitz  # PyMuPDF
import os
import hashlib
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from app.utils.logger import logger


class PDFExtractionError(Exception):
    """Custom exception for PDF extraction errors."""
    pass


class PDFExtractor:
    """Service for extracting text and metadata from PDF files."""

    @staticmethod
    def validate_pdf(file_path: str) -> bool:
        """
        Validate if a file is a valid PDF.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            True if valid PDF, False otherwise
        """
        try:
            with fitz.open(file_path) as doc:
                # Check if document is valid and has pages
                return len(doc) > 0
        except Exception as e:
            logger.warning(f"PDF validation failed for {file_path}: {str(e)}")
            return False

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> Dict[str, any]:
        """
        Extract text from all pages of a PDF file.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dictionary containing:
                - filename: Original filename
                - total_pages: Total number of pages
                - pages: List of page data with text and metadata
                - error: Error message if extraction failed
                
        Raises:
            PDFExtractionError: If PDF cannot be opened or read
        """
        if not os.path.exists(file_path):
            raise PDFExtractionError(f"File not found: {file_path}")

        try:
            result = {
                "filename": os.path.basename(file_path),
                "total_pages": 0,
                "pages": [],
                "error": None,
            }

            with fitz.open(file_path) as doc:
                result["total_pages"] = len(doc)

                if result["total_pages"] == 0:
                    raise PDFExtractionError("PDF has no pages")

                for page_num in range(result["total_pages"]):
                    try:
                        page = doc[page_num]
                        text = page.get_text()

                        # Skip empty pages
                        if not text.strip():
                            logger.debug(f"Page {page_num + 1} is empty in {result['filename']}")
                            continue

                        page_data = {
                            "page_number": page_num + 1,
                            "text": text,
                            "text_length": len(text),
                            "chunk_id": PDFExtractor._generate_chunk_id(
                                file_path, page_num + 1, text
                            ),
                        }
                        result["pages"].append(page_data)

                    except Exception as e:
                        logger.warning(f"Failed to extract text from page {page_num + 1}: {str(e)}")
                        continue

            if not result["pages"]:
                raise PDFExtractionError("No text could be extracted from any page")

            logger.info(
                f"Successfully extracted {len(result['pages'])} pages from {result['filename']}"
            )
            return result

        except Exception as e:
            error_str = str(e).lower()
            if "syntax error" in error_str or "cannot open" in error_str or "pdf" in error_str or "format" in error_str or "not a pdf" in error_str:
                raise PDFExtractionError(f"Invalid or corrupted PDF file: {str(e)}")
            raise PDFExtractionError(f"PDF extraction failed: {str(e)}")

    @staticmethod
    def _generate_chunk_id(file_path: str, page_number: int, text: str) -> str:
        """
        Generate a stable identifier for a text chunk.
        
        Args:
            file_path: Path to the PDF file
            page_number: Page number (1-indexed)
            text: Text content of the chunk
            
        Returns:
            Stable hash-based identifier
        """
        # Create a deterministic hash from filename, page number, and first 100 chars of text
        identifier = f"{os.path.basename(file_path)}:{page_number}:{text[:100]}"
        hash_obj = hashlib.sha256(identifier.encode())
        return hash_obj.hexdigest()[:16]

    @staticmethod
    def extract_pdf_metadata(file_path: str) -> Dict[str, any]:
        """
        Extract metadata from a PDF file.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dictionary containing PDF metadata
        """
        try:
            with fitz.open(file_path) as doc:
                metadata = doc.metadata or {}
                return {
                    "title": metadata.get("title", ""),
                    "author": metadata.get("author", ""),
                    "subject": metadata.get("subject", ""),
                    "creator": metadata.get("creator", ""),
                    "producer": metadata.get("producer", ""),
                    "creation_date": metadata.get("creationDate", ""),
                    "modification_date": metadata.get("modDate", ""),
                    "total_pages": len(doc),
                }
        except Exception as e:
            logger.warning(f"Failed to extract metadata from {file_path}: {str(e)}")
            return {"error": str(e)}

    @staticmethod
    def split_text_into_chunks(
        text: str, chunk_size: int = 1000, overlap: int = 100
    ) -> List[str]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Text to split
            chunk_size: Size of each chunk
            overlap: Number of characters to overlap between chunks
            
        Returns:
            List of text chunks
        """
        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap

        return chunks
