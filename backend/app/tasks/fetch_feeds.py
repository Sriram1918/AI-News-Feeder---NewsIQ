"""
RSS Feed Fetching Tasks

Celery tasks for fetching and processing RSS feeds.
"""

import asyncio
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from celery import shared_task
from sqlalchemy import select

from app.config.logging import get_logger
from app.db import get_db_context
from app.models import Article, RSSSource
from app.services.ingestion import (
    content_extractor,
    embedding_generator,
    rss_fetcher,
)

logger = get_logger(__name__)


def run_async(coro):
    """Run async function in sync context for Celery."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_all_feeds(self) -> dict:
    """
    Fetch all active RSS feeds.
    
    Runs every 5 minutes via Celery Beat.
    """
    return run_async(_fetch_all_feeds_async())


async def _fetch_all_feeds_async() -> dict:
    """Async implementation of feed fetching."""
    async with get_db_context() as db:
        # Get active sources
        result = await db.execute(
            select(RSSSource).where(RSSSource.is_active == True)
        )
        sources = list(result.scalars().all())
        
        logger.info("Starting RSS fetch", source_count=len(sources))
        
        total_articles = 0
        errors = 0
        
        for source in sources:
            try:
                articles = await _fetch_single_feed(db, source)
                total_articles += len(articles)
                source.mark_success()
                
            except Exception as e:
                logger.error(
                    "Failed to fetch feed",
                    source=source.name,
                    url=source.url,
                    error=str(e),
                )
                source.mark_failure(str(e))
                errors += 1
        
        await db.commit()
        
        logger.info(
            "RSS fetch complete",
            total_articles=total_articles,
            sources_processed=len(sources),
            errors=errors,
        )
        
        return {
            "total_articles": total_articles,
            "sources_processed": len(sources),
            "errors": errors,
        }


async def _fetch_single_feed(db, source: RSSSource) -> List[Article]:
    """Fetch and process a single RSS feed."""
    # Fetch and parse feed
    feed_articles = await rss_fetcher.fetch_and_parse(source.url)
    
    new_articles = []
    
    for article_data in feed_articles:
        # Check if article already exists
        result = await db.execute(
            select(Article).where(Article.url == article_data["url"])
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            continue
        
        # Extract full content if summary is short
        content = article_data.get("content", "")
        if len(content) < 500:
            extracted = await content_extractor.extract(article_data["url"])
            if extracted.success:
                content = extracted.content
                if not article_data.get("author") and extracted.author:
                    article_data["author"] = extracted.author
        
        # Skip if content is still too short
        if len(content) < 100:
            logger.debug("Skipping article with short content", url=article_data["url"])
            continue
        
        # Generate embedding
        try:
            embedding = await embedding_generator.generate(content[:10000])
        except Exception as e:
            logger.warning(
                "Failed to generate embedding",
                url=article_data["url"],
                error=str(e),
            )
            embedding = None
        
        # Create article
        article = Article(
            url=article_data["url"],
            title=article_data["title"],
            content=content,
            summary=article_data.get("summary"),
            author=article_data.get("author"),
            source=source.name,
            source_credibility_score=source.credibility_score,
            published_at=article_data["published_at"],
            embedding=embedding,
            topic_tags=article_data.get("tags"),
        )
        
        db.add(article)
        new_articles.append(article)
    
    if new_articles:
        await db.commit()
        logger.info(
            "Saved new articles",
            source=source.name,
            count=len(new_articles),
        )
    
    return new_articles


@shared_task
def fetch_single_source(source_id: str) -> dict:
    """Fetch a single RSS source by ID."""
    return run_async(_fetch_single_source_async(UUID(source_id)))


async def _fetch_single_source_async(source_id: UUID) -> dict:
    """Async implementation."""
    async with get_db_context() as db:
        result = await db.execute(
            select(RSSSource).where(RSSSource.id == source_id)
        )
        source = result.scalar_one_or_none()
        
        if not source:
            return {"error": "Source not found"}
        
        try:
            articles = await _fetch_single_feed(db, source)
            source.mark_success()
            await db.commit()
            
            return {
                "source": source.name,
                "articles": len(articles),
                "success": True,
            }
            
        except Exception as e:
            source.mark_failure(str(e))
            await db.commit()
            
            return {
                "source": source.name,
                "error": str(e),
                "success": False,
            }


@shared_task
def cleanup_expired_cache() -> dict:
    """Clean up expired research cache entries."""
    return run_async(_cleanup_cache_async())


async def _cleanup_cache_async() -> dict:
    """Async implementation."""
    from app.services.research import cache_manager
    
    async with get_db_context() as db:
        deleted = await cache_manager.cleanup_expired(db)
        
        return {
            "deleted_entries": deleted,
        }
