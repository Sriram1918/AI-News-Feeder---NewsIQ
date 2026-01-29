"""
Deep Research Retriever Service

Retrieves related articles for Deep Research using pgvector.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Set
from uuid import UUID

import numpy as np
from sqlalchemy import select, and_, not_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.logging import get_logger
from app.models import Article

logger = get_logger(__name__)


class Retriever:
    """
    Article Retriever for Deep Research.
    
    Features:
    - Vector similarity search
    - Entity overlap detection
    - Source diversity filtering
    """
    
    def __init__(self):
        """Initialize the retriever."""
        self.default_top_k = 5
        self.lookback_days = 30
        self.min_credibility = 60
    
    async def retrieve_related_articles(
        self,
        db: AsyncSession,
        article: Article,
        top_k: int = None,
    ) -> List[Article]:
        """
        Retrieve related articles for Deep Research.
        
        Multi-stage retrieval:
        1. Vector similarity (semantic)
        2. Entity overlap (same people/orgs mentioned)
        3. Source diversity filtering
        4. Credibility filtering
        
        Args:
            db: Database session.
            article: The main article to find related content for.
            top_k: Number of articles to return.
            
        Returns:
            List of related articles.
        """
        top_k = top_k or self.default_top_k
        
        if article.embedding is None:
            logger.warning("Article has no embedding", article_id=str(article.id))
            return []
        
        # Stage 1: Vector similarity search
        similar_articles = await self._vector_similarity_search(
            db=db,
            query_embedding=article.embedding,
            exclude_id=article.id,
            limit=top_k * 4,  # Over-fetch for filtering
        )
        
        # Stage 2: Entity overlap search (if entities available)
        entity_articles = []
        if article.entity_mentions:
            entity_articles = await self._entity_overlap_search(
                db=db,
                entities=article.entity_mentions,
                exclude_id=article.id,
                limit=top_k * 2,
            )
        
        # Stage 3: Combine and deduplicate
        all_candidates = self._combine_candidates(similar_articles, entity_articles)
        
        # Stage 4: Source diversity filtering
        diverse_articles = self._filter_for_source_diversity(
            candidates=all_candidates,
            main_source=article.source,
            target_count=top_k,
        )
        
        # Stage 5: Ensure credibility
        credible_articles = [
            a for a in diverse_articles
            if (a.source_credibility_score or 70) >= self.min_credibility
        ]
        
        logger.info(
            "Retrieved related articles",
            article_id=str(article.id),
            similar_count=len(similar_articles),
            entity_count=len(entity_articles),
            final_count=len(credible_articles[:top_k]),
        )
        
        return credible_articles[:top_k]
    
    async def _vector_similarity_search(
        self,
        db: AsyncSession,
        query_embedding: List[float],
        exclude_id: UUID,
        limit: int,
    ) -> List[Article]:
        """
        Perform vector similarity search.
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
        
        # Convert embedding if needed
        if not isinstance(query_embedding, list):
            query_embedding = query_embedding.tolist()
        
        query = (
            select(Article)
            .where(
                and_(
                    Article.embedding.isnot(None),
                    Article.id != exclude_id,
                    Article.published_at >= cutoff_date,
                )
            )
            .order_by(Article.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    async def _entity_overlap_search(
        self,
        db: AsyncSession,
        entities: dict,
        exclude_id: UUID,
        limit: int,
    ) -> List[Article]:
        """
        Find articles mentioning the same entities.
        """
        # Extract entity names
        people = entities.get("people", [])
        organizations = entities.get("organizations", [])
        locations = entities.get("locations", [])
        
        all_entities = set(people + organizations + locations)
        
        if not all_entities:
            return []
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
        
        # Search for articles with overlapping entities
        # Using JSONB containment operators
        matched_articles = []
        
        for entity in list(all_entities)[:5]:  # Limit to top 5 entities
            # Simple text search in entity_mentions JSONB
            query = (
                select(Article)
                .where(
                    and_(
                        Article.id != exclude_id,
                        Article.published_at >= cutoff_date,
                        Article.entity_mentions.isnot(None),
                    )
                )
                .limit(limit)
            )
            
            result = await db.execute(query)
            articles = result.scalars().all()
            
            # Filter by entity match
            for article in articles:
                if article.entity_mentions:
                    article_entities = set(
                        article.entity_mentions.get("people", []) +
                        article.entity_mentions.get("organizations", []) +
                        article.entity_mentions.get("locations", [])
                    )
                    if entity.lower() in [e.lower() for e in article_entities]:
                        matched_articles.append(article)
        
        return matched_articles[:limit]
    
    def _combine_candidates(
        self,
        similar: List[Article],
        entity_based: List[Article],
    ) -> List[Article]:
        """
        Combine and deduplicate candidate articles.
        """
        seen_ids: Set[UUID] = set()
        combined = []
        
        # Interleave similar and entity-based, preferring similar
        similar_iter = iter(similar)
        entity_iter = iter(entity_based)
        
        while True:
            # Add 2 similar
            for _ in range(2):
                try:
                    article = next(similar_iter)
                    if article.id not in seen_ids:
                        combined.append(article)
                        seen_ids.add(article.id)
                except StopIteration:
                    break
            
            # Add 1 entity-based
            try:
                article = next(entity_iter)
                if article.id not in seen_ids:
                    combined.append(article)
                    seen_ids.add(article.id)
            except StopIteration:
                pass
            
            # Break if both exhausted
            if len(combined) >= len(similar) + len(entity_based):
                break
        
        return combined
    
    def _filter_for_source_diversity(
        self,
        candidates: List[Article],
        main_source: str,
        target_count: int,
    ) -> List[Article]:
        """
        Filter to ensure source diversity.
        
        Goal: Get perspectives from different publishers.
        """
        used_sources: Set[str] = {main_source}
        diverse = []
        
        for article in candidates:
            if article.source not in used_sources:
                diverse.append(article)
                used_sources.add(article.source)
                
                if len(diverse) >= target_count:
                    break
        
        # If not enough diverse sources, fill with remaining
        if len(diverse) < target_count:
            for article in candidates:
                if article not in diverse:
                    diverse.append(article)
                    if len(diverse) >= target_count:
                        break
        
        return diverse


# Singleton instance
retriever = Retriever()
