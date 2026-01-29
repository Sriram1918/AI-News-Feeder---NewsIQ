"""
Research Cache Manager Service

Manages caching for Deep Research results.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.logging import get_logger
from app.config.settings import settings
from app.models import Article, ResearchCache

logger = get_logger(__name__)


class CacheManager:
    """
    Cache Manager for Deep Research results.
    
    Features:
    - 24-hour TTL caching
    - Cache invalidation on new related articles
    - View count tracking
    """
    
    def __init__(self):
        """Initialize the cache manager."""
        self.ttl_hours = settings.deep_research_cache_ttl_hours
        self.invalidation_threshold = 3  # New articles before invalidation
    
    async def get_cached_analysis(
        self,
        db: AsyncSession,
        article_id: UUID,
    ) -> Optional[ResearchCache]:
        """
        Get cached analysis for an article if valid.
        
        Args:
            db: Database session.
            article_id: Article ID.
            
        Returns:
            Valid cache entry or None.
        """
        now = datetime.now(timezone.utc)
        
        query = (
            select(ResearchCache)
            .where(
                ResearchCache.article_id == article_id,
                ResearchCache.invalidated == False,
                ResearchCache.expires_at > now,
            )
            .order_by(ResearchCache.generated_at.desc())
            .limit(1)
        )
        
        result = await db.execute(query)
        cache_entry = result.scalar_one_or_none()
        
        if cache_entry:
            # Increment view count
            cache_entry.view_count += 1
            await db.commit()
            
            logger.debug(
                "Cache hit",
                article_id=str(article_id),
                view_count=cache_entry.view_count,
            )
        
        return cache_entry
    
    async def store_analysis(
        self,
        db: AsyncSession,
        article_id: UUID,
        analysis_text: str,
        related_article_ids: list[UUID],
    ) -> ResearchCache:
        """
        Store analysis result in cache.
        
        Args:
            db: Database session.
            article_id: Article ID.
            analysis_text: Generated analysis.
            related_article_ids: IDs of related articles used.
            
        Returns:
            Created cache entry.
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=self.ttl_hours)
        
        cache_entry = ResearchCache(
            article_id=article_id,
            analysis_text=analysis_text,
            related_article_ids=related_article_ids,
            generated_at=now,
            expires_at=expires_at,
            view_count=1,
        )
        
        db.add(cache_entry)
        await db.commit()
        await db.refresh(cache_entry)
        
        logger.info(
            "Cached analysis",
            article_id=str(article_id),
            cache_id=str(cache_entry.id),
            expires_at=expires_at.isoformat(),
        )
        
        return cache_entry
    
    async def invalidate_cache(
        self,
        db: AsyncSession,
        article_id: UUID,
    ) -> int:
        """
        Invalidate cached analysis for an article.
        
        Args:
            db: Database session.
            article_id: Article ID.
            
        Returns:
            Number of cache entries invalidated.
        """
        result = await db.execute(
            update(ResearchCache)
            .where(
                ResearchCache.article_id == article_id,
                ResearchCache.invalidated == False,
            )
            .values(invalidated=True)
        )
        
        await db.commit()
        
        count = result.rowcount
        if count > 0:
            logger.info(
                "Invalidated cache",
                article_id=str(article_id),
                count=count,
            )
        
        return count
    
    async def cleanup_expired(
        self,
        db: AsyncSession,
    ) -> int:
        """
        Delete expired cache entries.
        
        Args:
            db: Database session.
            
        Returns:
            Number of entries deleted.
        """
        now = datetime.now(timezone.utc)
        
        result = await db.execute(
            delete(ResearchCache)
            .where(ResearchCache.expires_at < now)
        )
        
        await db.commit()
        
        count = result.rowcount
        if count > 0:
            logger.info("Cleaned expired cache entries", count=count)
        
        return count
    
    async def should_invalidate(
        self,
        db: AsyncSession,
        article: Article,
        cache_entry: ResearchCache,
    ) -> bool:
        """
        Check if cache should be invalidated due to new related articles.
        
        Args:
            db: Database session.
            article: Main article.
            cache_entry: Existing cache entry.
            
        Returns:
            True if cache should be invalidated.
        """
        if article.embedding is None:
            return False
        
        # Count new similar articles since cache generation
        from sqlalchemy import func
        
        # First, get the IDs of the most similar new articles (subquery)
        similar_subquery = (
            select(Article.id)
            .where(
                Article.embedding.isnot(None),
                Article.id != article.id,
                Article.fetched_at > cache_entry.generated_at,
            )
            .order_by(Article.embedding.cosine_distance(article.embedding))
            .limit(self.invalidation_threshold + 1)
        ).subquery()
        
        # Then count the results from the subquery
        query = select(func.count()).select_from(similar_subquery)
        
        result = await db.execute(query)
        new_count = result.scalar() or 0
        
        should_invalidate = new_count >= self.invalidation_threshold
        
        if should_invalidate:
            logger.debug(
                "Cache invalidation triggered",
                article_id=str(article.id),
                new_articles=new_count,
            )
        
        return should_invalidate


# Singleton instance
cache_manager = CacheManager()
