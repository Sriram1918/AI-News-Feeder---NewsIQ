"""
Feed Ranker Service

Implements personalized feed ranking with diversity injection.
Uses pgvector for efficient similarity search.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

import numpy as np
from pgvector.sqlalchemy import Vector
from sqlalchemy import select, text, and_, not_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.logging import get_logger
from app.config.settings import settings
from app.models import Article, User
from app.services.personalization.user_modeling import user_modeler

logger = get_logger(__name__)


class FeedRanker:
    """
    Feed Ranking Service.
    
    Generates personalized feeds using:
    - Vector similarity search with pgvector
    - User preference embeddings
    - Diversity injection (adjacent + blind spot articles)
    """
    
    def __init__(self):
        """Initialize the feed ranker."""
        self.diversity_percentage = settings.diversity_percentage  # 25%
        self.blind_spot_percentage = settings.blind_spot_percentage  # 5%
        self.default_lookback_days = 7
    
    async def get_personalized_feed(
        self,
        db: AsyncSession,
        user: User,
        limit: int = 20,
        offset: int = 0,
        include_blind_spots: bool = True,
    ) -> Tuple[List[Article], int]:
        """
        Generate personalized feed for user.
        
        Args:
            db: Database session.
            user: User object.
            limit: Number of articles to return.
            offset: Pagination offset.
            include_blind_spots: Whether to include diversity articles.
            
        Returns:
            Tuple of (articles, total_count).
        """
        # Get user vector
        user_vector = await user_modeler.get_combined_user_vector(db, user)
        
        if user_vector is None:
            # Cold start: Return recent popular articles
            logger.info("Cold start feed for user", user_id=str(user.id))
            return await self._get_recent_articles(db, user, limit, offset)
        
        # Get IDs of articles user has already interacted with (to exclude from feed)
        from app.models import UserInteraction
        viewed_query = (
            select(UserInteraction.article_id)
            .where(UserInteraction.user_id == user.id)
            .distinct()
        )
        viewed_result = await db.execute(viewed_query)
        viewed_article_ids = [row[0] for row in viewed_result.all()]
        
        # Calculate feed composition
        if include_blind_spots:
            main_count = int(limit * (100 - self.diversity_percentage) / 100)
            diverse_count = limit - main_count
        else:
            main_count = limit
            diverse_count = 0
        
        # Get main personalized articles (excluding already seen)
        main_articles = await self._vector_search(
            db=db,
            query_vector=user_vector,
            limit=main_count,
            offset=offset,
            muted_sources=user.muted_sources or [],
            exclude_ids=viewed_article_ids,
        )
        
        # Get diverse articles
        diverse_articles = []
        if diverse_count > 0:
            # Exclude both main articles and already viewed articles
            exclude_from_diverse = viewed_article_ids + [a.id for a in main_articles]
            # Calculate diverse offset based on how many diverse articles should have been shown before
            diverse_offset = (offset // limit) * diverse_count if offset > 0 else 0
            diverse_articles = await self._get_adjacent_diverse_articles(
                db=db,
                user_vector=user_vector,
                exclude_ids=exclude_from_diverse,
                muted_sources=user.muted_sources or [],
                limit=diverse_count,
                offset=diverse_offset,
            )
        
        # Interleave: 3 main, 1 diverse
        final_articles = self._interleave_articles(main_articles, diverse_articles)
        
        # Get total count
        total_count = await self._get_total_count(db, user.muted_sources or [])
        
        logger.info(
            "Generated personalized feed",
            user_id=str(user.id),
            main_count=len(main_articles),
            diverse_count=len(diverse_articles),
            total=len(final_articles),
        )
        
        return final_articles, total_count
    
    async def _vector_search(
        self,
        db: AsyncSession,
        query_vector: List[float],
        limit: int,
        offset: int = 0,
        muted_sources: List[str] = None,
        similarity_range: Tuple[float, float] = None,
        exclude_ids: List[UUID] = None,
        min_credibility: int = 0,
    ) -> List[Article]:
        """
        Perform vector similarity search using pgvector.
        
        Uses cosine distance (1 - cosine_similarity) for ranking.
        """
        muted_sources = muted_sources or []
        exclude_ids = exclude_ids or []
        
        # Build query with vector similarity
        # pgvector uses <=> for cosine distance
        vector_str = f"[{','.join(map(str, query_vector))}]"
        
        # Calculate date cutoff
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.default_lookback_days)
        
        # Build conditions
        conditions = [
            Article.embedding.isnot(None),
            Article.published_at >= cutoff_date,
        ]
        
        if muted_sources:
            conditions.append(not_(Article.source.in_(muted_sources)))
        
        if exclude_ids:
            conditions.append(not_(Article.id.in_(exclude_ids)))
        
        if min_credibility > 0:
            conditions.append(Article.source_credibility_score >= min_credibility)
        
        # Query with vector distance ordering
        # Using raw SQL for vector operations
        query = (
            select(Article)
            .where(and_(*conditions))
            .order_by(Article.embedding.cosine_distance(query_vector))
            .offset(offset)
            .limit(limit)
        )
        
        result = await db.execute(query)
        articles = list(result.scalars().all())
        
        # If similarity range specified, filter
        if similarity_range is not None:
            min_sim, max_sim = similarity_range
            filtered = []
            query_np = np.array(query_vector)
            
            for article in articles:
                if article.embedding is not None:
                    emb = np.array(article.embedding if isinstance(article.embedding, list) 
                                   else article.embedding.tolist())
                    sim = float(np.dot(query_np, emb) / (np.linalg.norm(query_np) * np.linalg.norm(emb) + 1e-10))
                    if min_sim <= sim <= max_sim:
                        filtered.append(article)
            
            return filtered
        
        return articles
    
    async def _get_adjacent_diverse_articles(
        self,
        db: AsyncSession,
        user_vector: List[float],
        exclude_ids: List[UUID],
        muted_sources: List[str],
        limit: int,
        offset: int = 0,
    ) -> List[Article]:
        """
        Get adjacent diverse articles (related but different perspectives).
        
        Targets articles with similarity between 0.5 and 0.8.
        """
        # Over-fetch to allow filtering (account for offset)
        candidates = await self._vector_search(
            db=db,
            query_vector=user_vector,
            limit=limit * 5,
            offset=offset,  # Respect pagination for diverse articles too
            muted_sources=muted_sources,
            exclude_ids=exclude_ids,
            min_credibility=70,  # Only credible sources for diversity
        )
        
        # Filter by similarity range
        diverse = []
        query_np = np.array(user_vector)
        
        for article in candidates:
            if article.embedding is not None:
                emb = np.array(article.embedding if isinstance(article.embedding, list) 
                               else article.embedding.tolist())
                sim = float(np.dot(query_np, emb) / (np.linalg.norm(query_np) * np.linalg.norm(emb) + 1e-10))
                
                # Adjacent diversity: not too similar, not too different
                if 0.4 <= sim <= 0.75:
                    diverse.append(article)
                    if len(diverse) >= limit:
                        break
        
        # Mark as blind spot articles
        for article in diverse:
            # This attribute is transient, not stored in DB
            article._is_blind_spot = True
        
        return diverse
    
    async def _get_recent_articles(
        self,
        db: AsyncSession,
        user: User,
        limit: int,
        offset: int,
    ) -> Tuple[List[Article], int]:
        """
        Get recent articles for cold start users.
        
        Filters by user's preference_topics if available.
        """
        from app.models import RSSSource
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
        muted_sources = user.muted_sources or []
        preference_topics = user.preference_topics or []
        
        conditions = [
            Article.published_at >= cutoff_date,
        ]
        
        if muted_sources:
            conditions.append(not_(Article.source.in_(muted_sources)))
        
        # If user has preference topics, filter articles from those categories
        if preference_topics:
            # Get sources that match user's preferred topics
            source_query = (
                select(RSSSource.name)
                .where(RSSSource.category.in_(preference_topics))
            )
            source_result = await db.execute(source_query)
            preferred_sources = [row[0] for row in source_result.all()]
            
            if preferred_sources:
                conditions.append(Article.source.in_(preferred_sources))
                logger.info(
                    "Filtering cold start feed by topics",
                    user_id=str(user.id),
                    topics=preference_topics,
                    sources=preferred_sources,
                )
        
        query = (
            select(Article)
            .where(and_(*conditions))
            .order_by(Article.published_at.desc())
            .offset(offset)
            .limit(limit)
        )
        
        result = await db.execute(query)
        articles = list(result.scalars().all())
        
        total_count = await self._get_total_count(db, muted_sources)
        
        return articles, total_count
    
    async def _get_total_count(
        self,
        db: AsyncSession,
        muted_sources: List[str],
    ) -> int:
        """Get total article count for pagination."""
        from sqlalchemy import func
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.default_lookback_days)
        
        conditions = [Article.published_at >= cutoff_date]
        if muted_sources:
            conditions.append(not_(Article.source.in_(muted_sources)))
        
        query = select(func.count(Article.id)).where(and_(*conditions))
        result = await db.execute(query)
        return result.scalar() or 0
    
    def _interleave_articles(
        self,
        main: List[Article],
        diverse: List[Article],
    ) -> List[Article]:
        """
        Interleave main and diverse articles.
        
        Pattern: 3 main, 1 diverse, repeat.
        """
        result = []
        main_idx = 0
        diverse_idx = 0
        
        while main_idx < len(main) or diverse_idx < len(diverse):
            # Add 3 main articles
            for _ in range(3):
                if main_idx < len(main):
                    result.append(main[main_idx])
                    main_idx += 1
            
            # Add 1 diverse article
            if diverse_idx < len(diverse):
                result.append(diverse[diverse_idx])
                diverse_idx += 1
        
        return result


# Singleton instance
feed_ranker = FeedRanker()
