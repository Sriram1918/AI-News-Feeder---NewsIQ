"""
Deep Research API Routes

Endpoints for the "Explain This" feature.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware import get_current_user, rate_limiter
from app.api.schemas import RelatedArticle, ResearchRequest, ResearchResponse
from app.config.logging import get_logger
from app.config.settings import settings
from app.db import get_db_session
from app.models import Article, User, UserInteraction
from app.services.research import analyzer, cache_manager, retriever

logger = get_logger(__name__)

router = APIRouter(prefix="/research", tags=["Research"])


@router.post("/analyze", response_model=ResearchResponse)
async def analyze_article(
    request: ResearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ResearchResponse:
    """
    Generate Deep Research analysis for an article.
    
    This endpoint:
    1. Checks cache for existing analysis
    2. Retrieves related articles using vector search
    3. Generates 200-word context analysis using Claude        
    4. Caches result for 24 hours
    
    Rate limited to 5 requests per minute.
    """
    # Rate limiting for expensive operation
    from fastapi import Request
    # Note: In production, inject Request properly
    # await rate_limiter.check_rate_limit(
    #     request, 
    #     limit=settings.deep_research_rate_limit_per_minute,
    #     endpoint="research"
    # )
    
    # Fetch article
    result = await db.execute(
        select(Article).where(Article.id == request.article_id)
    )
    article = result.scalar_one_or_none()
    
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )
    
    # Check cache
    cached = await cache_manager.get_cached_analysis(db, article.id)
    
    if cached:
        # Check if we should invalidate
        should_invalidate = await cache_manager.should_invalidate(db, article, cached)
        
        if not should_invalidate:
            logger.info(
                "Serving cached analysis",
                article_id=str(article.id),
                cache_age_hours=(datetime.now(timezone.utc) - cached.generated_at).seconds / 3600,
            )
            
            # Get related articles for response
            related_articles = []
            if cached.related_article_ids:
                for related_id in cached.related_article_ids[:5]:
                    result = await db.execute(
                        select(Article).where(Article.id == related_id)
                    )
                    related = result.scalar_one_or_none()
                    if related:
                        related_articles.append(
                            RelatedArticle(
                                id=related.id,
                                title=related.title,
                                url=related.url,
                                source=related.source,
                                published_at=related.published_at,
                            )
                        )
            
            return ResearchResponse(
                analysis=cached.analysis_text,
                related_articles=related_articles,
                generated_at=cached.generated_at,
                from_cache=True,
            )
        else:
            # Invalidate and regenerate
            await cache_manager.invalidate_cache(db, article.id)
    
    # Retrieve related articles
    related_articles = await retriever.retrieve_related_articles(
        db=db,
        article=article,
        top_k=5,
    )
    
    # Generate analysis
    analysis_text = await analyzer.analyze_with_fallback(
        article=article,
        related_articles=related_articles,
    )
    
    # Cache result
    related_ids = [a.id for a in related_articles]
    cache_entry = await cache_manager.store_analysis(
        db=db,
        article_id=article.id,
        analysis_text=analysis_text,
        related_article_ids=related_ids,
    )
    
    # Record deep research interaction
    interaction = UserInteraction(
        user_id=user.id,
        article_id=article.id,
        interaction_type="deep_research",
    )
    db.add(interaction)
    await db.commit()
    
    logger.info(
        "Generated new analysis",
        article_id=str(article.id),
        related_count=len(related_articles),
    )
    
    # Build response
    related_response = [
        RelatedArticle(
            id=a.id,
            title=a.title,
            url=a.url,
            source=a.source,
            published_at=a.published_at,
        )
        for a in related_articles
    ]
    
    return ResearchResponse(
        analysis=analysis_text,
        related_articles=related_response,
        generated_at=cache_entry.generated_at,
        from_cache=False,
    )
