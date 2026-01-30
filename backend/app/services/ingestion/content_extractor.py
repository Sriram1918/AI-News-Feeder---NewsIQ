"""
Content Extractor Service

Extracts full article content from URLs using Trafilatura.
Following official Trafilatura documentation:
https://trafilatura.readthedocs.io/
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional

import httpx
import trafilatura
from trafilatura.settings import use_config

from app.config.logging import get_logger
from app.config.settings import settings

logger = get_logger(__name__)


@dataclass
class ExtractedContent:
    """Dataclass for extracted article content."""
    title: Optional[str]
    content: str
    author: Optional[str]
    date: Optional[str]
    description: Optional[str]
    sitename: Optional[str]
    extraction_method: str
    success: bool
    error: Optional[str] = None


class ContentExtractionError(Exception):
    """Exception raised when content extraction fails."""
    pass


class ContentExtractor:
    """
    Content Extractor using Trafilatura.
    
    Features:
    - Full article content extraction
    - Metadata extraction (author, date, etc.)
    - Fallback strategies
    - Async wrapper for thread-pool execution
    """
    
    def __init__(self):
        """Initialize the content extractor."""
        # Configure Trafilatura
        self.config = use_config()
        self.config.set("DEFAULT", "EXTRACTION_TIMEOUT", str(settings.content_extraction_timeout))
        self.config.set("DEFAULT", "MIN_OUTPUT_SIZE", "200")  # Minimum content length
        self.config.set("DEFAULT", "MIN_EXTRACTED_SIZE", "100")
        
        # Thread pool for running sync trafilatura in async context
        self._executor = ThreadPoolExecutor(max_workers=4)
    
    async def fetch_url(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from URL.
        
        Args:
            url: URL to fetch.
            
        Returns:
            HTML content or None if fetch fails.
        """
        async with httpx.AsyncClient(
            timeout=settings.content_extraction_timeout,
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                    },
                )
                response.raise_for_status()
                return response.text
                
            except httpx.HTTPStatusError as e:
                logger.warning(
                    "HTTP error fetching URL",
                    url=url,
                    status_code=e.response.status_code,
                )
                return None
                
            except Exception as e:
                logger.warning("Error fetching URL", url=url, error=str(e))
                return None
    
    def _extract_sync(self, html: str, url: str) -> ExtractedContent:
        """
        Synchronous extraction using Trafilatura.
        
        This runs in a thread pool to avoid blocking.
        """
        try:
            # Extract with Trafilatura
            # Use bare_extraction which returns a dict directly
            result = trafilatura.bare_extraction(
                html,
                url=url,
                include_comments=False,
                include_tables=False,
                include_images=False,
                include_links=False,
                include_formatting=False,
                config=self.config,
            )
            
            if result is None:
                # Fallback: Try bare extraction
                text = trafilatura.extract(
                    html,
                    url=url,
                    include_comments=False,
                    include_tables=False,
                    favor_recall=True,
                    config=self.config,
                )
                
                if text and len(text) > 100:
                    return ExtractedContent(
                        title=None,
                        content=text,
                        author=None,
                        date=None,
                        description=None,
                        sitename=None,
                        extraction_method="trafilatura_fallback",
                        success=True,
                    )
                
                return ExtractedContent(
                    title=None,
                    content="",
                    author=None,
                    date=None,
                    description=None,
                    sitename=None,
                    extraction_method="trafilatura",
                    success=False,
                    error="No content extracted",
                )
            
            # Check if result is dict (from output_format='python')
            # In newer trafilatura versions, result might be a Document object
            if hasattr(result, 'text'):
                # It's a Document object
                content = result.text or ""
                if len(content) < 100:
                    return ExtractedContent(
                        title=getattr(result, 'title', None),
                        content=content,
                        author=getattr(result, 'author', None),
                        date=getattr(result, 'date', None),
                        description=getattr(result, 'description', None),
                        sitename=getattr(result, 'sitename', None),
                        extraction_method="trafilatura",
                        success=False,
                        error="Content too short",
                    )
                
                return ExtractedContent(
                    title=getattr(result, 'title', None),
                    content=content,
                    author=getattr(result, 'author', None),
                    date=getattr(result, 'date', None),
                    description=getattr(result, 'description', None),
                    sitename=getattr(result, 'sitename', None),
                    extraction_method="trafilatura",
                    success=True,
                )
            elif isinstance(result, dict):
                content = result.get("text", "")
                if len(content) < 100:
                    return ExtractedContent(
                        title=result.get("title"),
                        content=content,
                        author=result.get("author"),
                        date=result.get("date"),
                        description=result.get("description"),
                        sitename=result.get("sitename"),
                        extraction_method="trafilatura",
                        success=False,
                        error="Content too short",
                    )
                
                return ExtractedContent(
                    title=result.get("title"),
                    content=content,
                    author=result.get("author"),
                    date=result.get("date"),
                    description=result.get("description"),
                    sitename=result.get("sitename"),
                    extraction_method="trafilatura",
                    success=True,
                )
            
            # Result is plain text
            if len(result) < 100:
                return ExtractedContent(
                    title=None,
                    content=result,
                    author=None,
                    date=None,
                    description=None,
                    sitename=None,
                    extraction_method="trafilatura",
                    success=False,
                    error="Content too short",
                )
            
            return ExtractedContent(
                title=None,
                content=result,
                author=None,
                date=None,
                description=None,
                sitename=None,
                extraction_method="trafilatura",
                success=True,
            )
            
        except Exception as e:
            logger.error("Extraction error", url=url, error=str(e))
            return ExtractedContent(
                title=None,
                content="",
                author=None,
                date=None,
                description=None,
                sitename=None,
                extraction_method="trafilatura",
                success=False,
                error=str(e),
            )
    
    async def extract(self, url: str, html: Optional[str] = None) -> ExtractedContent:
        """
        Extract article content from URL.
        
        Args:
            url: Article URL.
            html: Optional pre-fetched HTML content.
            
        Returns:
            ExtractedContent with article data.
        """
        # Fetch HTML if not provided
        if html is None:
            html = await self.fetch_url(url)
            if html is None:
                return ExtractedContent(
                    title=None,
                    content="",
                    author=None,
                    date=None,
                    description=None,
                    sitename=None,
                    extraction_method="fetch_failed",
                    success=False,
                    error="Failed to fetch URL",
                )
        
        # Run extraction in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor,
            self._extract_sync,
            html,
            url,
        )
        
        if result.success:
            logger.info(
                "Content extracted successfully",
                url=url,
                content_length=len(result.content),
                method=result.extraction_method,
            )
        else:
            logger.warning(
                "Content extraction failed",
                url=url,
                error=result.error,
            )
        
        return result
    
    async def extract_batch(
        self,
        urls: list[str],
        max_concurrent: int = 5,
    ) -> list[ExtractedContent]:
        """
        Extract content from multiple URLs concurrently.
        
        Args:
            urls: List of URLs to extract.
            max_concurrent: Maximum concurrent extractions.
            
        Returns:
            List of ExtractedContent results.
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def extract_with_semaphore(url: str) -> ExtractedContent:
            async with semaphore:
                return await self.extract(url)
        
        tasks = [extract_with_semaphore(url) for url in urls]
        return await asyncio.gather(*tasks)


# Singleton instance
content_extractor = ContentExtractor()
