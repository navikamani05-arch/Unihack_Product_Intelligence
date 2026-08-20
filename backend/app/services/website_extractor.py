"""Website extraction service using BeautifulSoup and Requests."""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from typing import Dict, Optional, List
import hashlib
from app.utils.logger import logger
from app.config import settings


class WebsiteExtractionError(Exception):
    """Custom exception for website extraction errors."""
    pass


class WebsiteExtractor:
    """Service for extracting product information from websites."""

    TIMEOUT = settings.request_timeout_seconds
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    @staticmethod
    def validate_url(url: str) -> bool:
        """
        Validate if a URL is properly formatted.
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid URL format, False otherwise
        """
        try:
            result = urlparse(url)
            return all([result.scheme in ['http', 'https'], result.netloc])
        except Exception:
            return False

    @staticmethod
    def fetch_webpage(url: str) -> str:
        """
        Fetch webpage content.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content as string
            
        Raises:
            WebsiteExtractionError: If fetch fails
        """
        if not WebsiteExtractor.validate_url(url):
            raise WebsiteExtractionError(f"Invalid URL format: {url}")

        try:
            response = requests.get(
                url,
                headers=WebsiteExtractor.HEADERS,
                timeout=WebsiteExtractor.TIMEOUT,
                allow_redirects=True,
            )
            response.raise_for_status()
            
            if not response.text:
                raise WebsiteExtractionError("Webpage returned empty content")
            
            return response.text

        except requests.exceptions.Timeout:
            raise WebsiteExtractionError(f"Request timeout: {url}")
        except requests.exceptions.ConnectionError:
            raise WebsiteExtractionError(f"Connection failed: {url}")
        except requests.exceptions.HTTPError as e:
            raise WebsiteExtractionError(f"HTTP error {e.response.status_code}: {url}")
        except requests.exceptions.RequestException as e:
            raise WebsiteExtractionError(f"Request failed: {str(e)}")

    @staticmethod
    def extract_content_from_html(html: str, url: str) -> Dict[str, any]:
        """
        Extract product-relevant content from HTML.
        
        Args:
            html: HTML content
            url: Original URL
            
        Returns:
            Dictionary containing:
                - url: Original URL
                - title: Page title
                - headings: List of headings
                - paragraphs: List of paragraphs
                - text: Full extracted text
                - chunks: List of text chunks
                - error: Error message if extraction failed
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style", "meta", "link"]):
                script.decompose()

            # Extract title
            title = ""
            if soup.title:
                title = soup.title.string or ""

            # Extract headings
            headings = []
            for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                text = heading.get_text(strip=True)
                if text:
                    headings.append(text)

            # Extract main content - look for common product content containers
            main_content = soup.find_all(['main', 'article', 'section', 'div'])
            
            # Extract paragraphs and product-related content
            paragraphs = []
            for tag in soup.find_all(['p', 'li', 'td', 'span']):
                text = tag.get_text(strip=True)
                if text and len(text) > 20:  # Filter out very short text
                    paragraphs.append(text)

            # Extract all text and clean it
            full_text = soup.get_text(separator='\n', strip=True)
            
            # Split into chunks
            chunks = WebsiteExtractor._split_text_into_chunks(full_text)

            if not chunks:
                raise WebsiteExtractionError("No content could be extracted from webpage")

            logger.info(f"Successfully extracted content from {url}")

            return {
                "url": url,
                "title": title,
                "headings": headings,
                "paragraphs": paragraphs,
                "text": full_text,
                "chunks": chunks,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Content extraction error: {str(e)}")
            raise WebsiteExtractionError(f"Failed to extract content: {str(e)}")

    @staticmethod
    def extract_website_data(url: str) -> Dict[str, any]:
        """
        Extract product data from a website.
        
        Args:
            url: Website URL
            
        Returns:
            Dictionary with extracted website data
        """
        try:
            # Fetch webpage
            html = WebsiteExtractor.fetch_webpage(url)
            
            # Extract content
            content = WebsiteExtractor.extract_content_from_html(html, url)
            
            return content

        except WebsiteExtractionError as e:
            logger.error(f"Website extraction error: {str(e)}")
            return {
                "url": url,
                "error": str(e),
                "title": None,
                "headings": [],
                "paragraphs": [],
                "text": None,
                "chunks": [],
            }

    @staticmethod
    def _split_text_into_chunks(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Text to split
            chunk_size: Size of each chunk
            overlap: Number of characters to overlap
            
        Returns:
            List of text chunks
        """
        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk)
            start = end - overlap

        return chunks

    @staticmethod
    def generate_chunk_id(url: str, chunk_index: int, text: str) -> str:
        """
        Generate a stable identifier for a website content chunk.
        
        Args:
            url: Website URL
            chunk_index: Index of chunk
            text: Text content
            
        Returns:
            Stable hash-based identifier
        """
        identifier = f"{url}:{chunk_index}:{text[:100]}"
        hash_obj = hashlib.sha256(identifier.encode())
        return hash_obj.hexdigest()[:16]
