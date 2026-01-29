"""
RSS Feed Fetcher Service

Fetches and parses RSS feeds using feedparser.
Following official feedparser documentation:
https://feedparser.readthedocs.io/
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import feedparser
import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config.logging import get_logger
from app.config.settings import settings

logger = get_logger(__name__)


class RSSFetchError(Exception):
    """Exception raised when RSS fetch fails."""
    pass


class RSSFetcher:
    """
    RSS Feed Fetcher.
    
    Fetches and parses RSS feeds with:
    - Async HTTP requests using httpx
    - Retry logic with exponential backoff
    - Rate limiting per domain
    - Error handling and logging
    """
    
    def __init__(self):
        """Initialize the RSS fetcher."""
        self._domain_last_fetch: Dict[str, datetime] = {}
        self._rate_limit_seconds = 1.0  # Minimum seconds between requests to same domain
        
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc
    
    async def _wait_for_rate_limit(self, domain: str) -> None:
        """Wait if needed to respect rate limit for domain."""
        if domain in self._domain_last_fetch:
            elapsed = (datetime.now(timezone.utc) - self._domain_last_fetch[domain]).total_seconds()
            if elapsed < self._rate_limit_seconds:
                await asyncio.sleep(self._rate_limit_seconds - elapsed)
        self._domain_last_fetch[domain] = datetime.now(timezone.utc)
    
    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def fetch_feed_content(self, url: str) -> str:
        """
        Fetch raw RSS feed content from URL.
        
        Args:
            url: The RSS feed URL.
            
        Returns:
            Raw XML content of the feed.
            
        Raises:
            RSSFetchError: If fetch fails after retries.
        """
        domain = self._get_domain(url)
        await self._wait_for_rate_limit(domain)
        
        async with httpx.AsyncClient(
            timeout=settings.content_extraction_timeout,
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "NewsIntelligenceBot/1.0 (compatible; RSS Reader)",
                        "Accept": "application/rss+xml, application/xml, text/xml",
                    },
                )
                response.raise_for_status()
                
                logger.debug(
                    "Fetched RSS feed",
                    url=url,
                    status_code=response.status_code,
                    content_length=len(response.content),
                )
                
                return response.text
                
            except httpx.HTTPStatusError as e:
                logger.error(
                    "HTTP error fetching RSS feed",
                    url=url,
                    status_code=e.response.status_code,
                    error=str(e),
                )
                raise RSSFetchError(f"HTTP {e.response.status_code}: {str(e)}")
                
            except httpx.TimeoutException as e:
                logger.error("Timeout fetching RSS feed", url=url, error=str(e))
                raise RSSFetchError(f"Timeout: {str(e)}")
    
    def parse_feed(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse RSS feed content into article entries.
        
        Args:
            content: Raw XML content of the feed.
            
        Returns:
            List of parsed article dictionaries with normalized fields.
        """
        feed = feedparser.parse(content)
        
        if feed.bozo and feed.bozo_exception:
            logger.warning(
                "Feed parsing had issues",
                error=str(feed.bozo_exception),
            )
        
        articles = []
        
        for entry in feed.entries:
            article = self._normalize_entry(entry, feed.feed)
            if article:
                articles.append(article)
        
        logger.info(
            "Parsed RSS feed",
            feed_title=feed.feed.get("title", "Unknown"),
            article_count=len(articles),
        )
        
        return articles
    
    def _normalize_entry(
        self,
        entry: feedparser.FeedParserDict,
        feed_meta: feedparser.FeedParserDict,
    ) -> Optional[Dict[str, Any]]:
        """
        Normalize a feed entry to standard article format.
        
        Args:
            entry: The feedparser entry object.
            feed_meta: The feed metadata.
            
        Returns:
            Normalized article dictionary or None if entry is invalid.
        """
        # Required fields
        url = entry.get("link")
        title = entry.get("title")
        
        if not url or not title:
            logger.debug("Skipping entry without URL or title")
            return None
        
        # Parse published date
        published_at = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
        
        if not published_at and hasattr(entry, "updated_parsed") and entry.updated_parsed:
            try:
                published_at = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
        
        # Default to current time if no date found
        if not published_at:
            published_at = datetime.now(timezone.utc)
        
        # Extract content/summary
        content = ""
        if hasattr(entry, "content") and entry.content:
            content = entry.content[0].get("value", "")
        elif hasattr(entry, "summary"):
            content = entry.summary or ""
        elif hasattr(entry, "description"):
            content = entry.description or ""
        
        # Extract author
        author = None
        if hasattr(entry, "author"):
            author = entry.author
        elif hasattr(entry, "author_detail"):
            author = entry.author_detail.get("name")
        
        # Extract source name
        source = feed_meta.get("title", "Unknown Source")
        
        return {
            "url": url,
            "title": self._clean_html(title),
            "content": self._clean_html(content),
            "summary": self._clean_html(entry.get("summary", ""))[:500] if entry.get("summary") else None,
            "author": author,
            "source": source,
            "published_at": published_at,
            "tags": [tag.term for tag in getattr(entry, "tags", [])],
        }
    
    def _clean_html(self, text: str) -> str:
        """
        Remove HTML tags from text.
        
        Uses a simple regex-based approach. For complex HTML,
        consider using BeautifulSoup.
        """
        import re
        if not text:
            return ""
        
        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", "", text)
        # Normalize whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        # Decode HTML entities
        import html
        clean = html.unescape(clean)
        
        return clean
    
    async def fetch_and_parse(self, url: str) -> List[Dict[str, Any]]:
        """
        Fetch and parse an RSS feed in one call.
        
        Args:
            url: The RSS feed URL.
            
        Returns:
            List of parsed article dictionaries.
            
        Raises:
            RSSFetchError: If fetch or parse fails.
        """
        try:
            content = await self.fetch_feed_content(url)
            articles = self.parse_feed(content)
            return articles
        except Exception as e:
            logger.error("Failed to fetch and parse feed", url=url, error=str(e))
            raise RSSFetchError(f"Failed to fetch feed: {str(e)}")


# Singleton instance for convenience
rss_fetcher = RSSFetcher()
