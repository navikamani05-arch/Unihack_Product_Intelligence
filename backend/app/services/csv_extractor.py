"""CSV extraction service using Pandas."""
import pandas as pd
import io
from typing import Dict, List, Optional, Tuple
import hashlib
from app.utils.logger import logger


class CSVExtractionError(Exception):
    """Custom exception for CSV extraction errors."""
    pass


class CSVExtractor:
    """Service for extracting product data from CSV files."""

    @staticmethod
    def validate_csv(content: bytes) -> bool:
        """
        Validate if content is a valid CSV.
        
        Args:
            content: File content as bytes
            
        Returns:
            True if valid CSV, False otherwise
        """
        try:
            df = pd.read_csv(io.BytesIO(content), nrows=1)
            return len(df) >= 0  # At least header row
        except Exception as e:
            logger.warning(f"CSV validation failed: {str(e)}")
            return False

    @staticmethod
    def extract_csv_data(content: bytes, filename: str) -> Dict[str, any]:
        """
        Extract data from CSV file.
        
        Args:
            content: File content as bytes
            filename: Original filename
            
        Returns:
            Dictionary containing:
                - filename: Original filename
                - total_rows: Number of data rows
                - columns: List of column names
                - rows: List of row data
                - error: Error message if extraction failed
        """
        try:
            # Read CSV
            df = pd.read_csv(io.BytesIO(content))

            if df.empty:
                raise CSVExtractionError("CSV file is empty")

            # Get column names
            columns = df.columns.tolist()

            # Convert rows to list of dicts with row numbers
            rows = []
            for idx, (_, row) in enumerate(df.iterrows(), start=1):
                row_data = {
                    "row_number": idx,
                    "values": row.to_dict(),
                    "chunk_id": CSVExtractor._generate_chunk_id(filename, idx, row),
                }
                rows.append(row_data)

            logger.info(f"Successfully extracted {len(rows)} rows from {filename}")

            return {
                "filename": filename,
                "total_rows": len(rows),
                "columns": columns,
                "rows": rows,
                "error": None,
            }

        except pd.errors.ParserError as e:
            raise CSVExtractionError(f"CSV parsing error: {str(e)}")
        except Exception as e:
            raise CSVExtractionError(f"CSV extraction failed: {str(e)}")

    @staticmethod
    def detect_product_columns(columns: List[str]) -> Dict[str, Optional[str]]:
        """
        Detect product-related columns in CSV.
        
        Args:
            columns: List of column names
            
        Returns:
            Dictionary mapping standard fields to detected columns
        """
        column_lower = [col.lower() for col in columns]
        
        # Define common product field patterns
        field_patterns = {
            "sku": ["sku", "product_id", "part_number", "code"],
            "name": ["name", "product_name", "title", "description"],
            "brand": ["brand", "manufacturer", "maker"],
            "category": ["category", "type", "class"],
            "price": ["price", "cost", "value"],
            "voltage": ["voltage", "v", "volts"],
            "power": ["power", "watts", "w", "wattage"],
            "material": ["material", "composition"],
        }

        detected = {}
        for field, patterns in field_patterns.items():
            for pattern in patterns:
                for idx, col_lower in enumerate(column_lower):
                    if pattern in col_lower or col_lower == pattern:
                        detected[field] = columns[idx]
                        break
            if field not in detected:
                detected[field] = None

        return detected

    @staticmethod
    def _generate_chunk_id(filename: str, row_number: int, row_data) -> str:
        """
        Generate a stable identifier for a CSV row.
        
        Args:
            filename: CSV filename
            row_number: Row number (1-indexed)
            row_data: Row data (pandas Series)
            
        Returns:
            Stable hash-based identifier
        """
        # Create identifier from filename, row number, and first value
        first_value = str(row_data.iloc[0]) if len(row_data) > 0 else ""
        identifier = f"{filename}:{row_number}:{first_value[:50]}"
        hash_obj = hashlib.sha256(identifier.encode())
        return hash_obj.hexdigest()[:16]

    @staticmethod
    def row_to_text(row_dict: Dict, columns: List[str]) -> str:
        """
        Convert a CSV row to readable text format.
        
        Args:
            row_dict: Row data as dictionary
            columns: List of column names
            
        Returns:
            Formatted text representation
        """
        lines = []
        for col in columns:
            value = row_dict.get(col, "")
            if pd.notna(value) and str(value).strip():
                lines.append(f"{col}: {value}")
        return "\n".join(lines)
