"""
Feed API Routes

Endpoints for personalized news feed.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware import get_current_user, get_current_user_optional
from app.api.schemas import (
    ArticleDetailResponse,
    ArticleResponse,
    FeedResponse,
)
from app.config.logging import get_logger
from app.db import get_db_session
from app.models import Article, User, UserInteraction
from app.services.personalization import feed_ranker

logger = get_logger(__name__)   

router = APIRouter(prefix="/feed", tags=["Feed"])


@router.get("", response_model=FeedResponse)
async def get_feed(
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=20, ge=1, le=50, description="Items per page"),
    include_blind_spots: bool = Query(
        default=True,
        description="Include diversity articles",
    ),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
) -> FeedResponse:
    """
    Get personalized news feed.
    
    Returns articles ranked by user preferences with diversity injection.
    For unauthenticated users, returns recent articles chronologically.
    """
    offset = (page - 1) * per_page
    
    if user:
        # Personalized feed for authenticated users
        articles, total_count = await feed_ranker.get_personalized_feed(
            db=db,
            user=user,
            limit=per_page,
            offset=offset,
            include_blind_spots=include_blind_spots,
        )
        
        logger.info(
            "Generated personalized feed",
            user_id=str(user.id),
            page=page,
            articles_count=len(articles),
        )
    else:
        # Chronological feed for anonymous users
        from datetime import datetime, timedelta, timezone
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        
        query = (
            select(Article)
            .where(Article.published_at >= cutoff)
            .order_by(Article.published_at.desc())
            .offset(offset)
            .limit(per_page)
        )
        
        result = await db.execute(query)
        articles = list(result.scalars().all())
        
        # Get total count
        from sqlalchemy import func
        count_query = select(func.count(Article.id)).where(Article.published_at >= cutoff)
        count_result = await db.execute(count_query)
        total_count = count_result.scalar() or 0
        
        logger.info(
            "Generated anonymous feed",
            page=page,
            articles_count=len(articles),
        )
    
    # Convert to response format
    article_responses = []
    for article in articles:
        is_blind_spot = getattr(article, "_is_blind_spot", False)
        
        # Estimate read time (assuming 200 words per minute)
        word_count = len(article.content.split()) if article.content else 0
        read_time = max(1, word_count // 200)
        
        article_responses.append(
            ArticleResponse(
                id=article.id,
                title=article.title,
                url=article.url,
                summary=article.summary,
                author=article.author,
                source=article.source,
                source_credibility_score=article.source_credibility_score,
                published_at=article.published_at,
                topic_tags=article.topic_tags,
                sentiment_score=article.sentiment_score,
                is_blind_spot=is_blind_spot,
                read_time_minutes=read_time,
            )
        )
    
    has_more = offset + len(articles) < total_count
    
    return FeedResponse(
        articles=article_responses,
        has_more=has_more,
        total_count=total_count,
        page=page,
        per_page=per_page,
    )


@router.get("/bookmarks", response_model=FeedResponse)
async def get_bookmarks(
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=20, ge=1, le=50, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> FeedResponse:
    """
    Get user's bookmarked articles.
    """
    offset = (page - 1) * per_page
    
    # Get bookmarked article IDs
    bookmark_query = (
        select(UserInteraction.article_id)
        .where(
            UserInteraction.user_id == user.id,
            UserInteraction.interaction_type == "bookmark"
        )
        .order_by(UserInteraction.created_at.desc())
    )
    result = await db.execute(bookmark_query)
    bookmarked_ids = [row[0] for row in result.all()]
    
    if not bookmarked_ids:
        return FeedResponse(
            articles=[],
            has_more=False,
            total_count=0,
            page=page,
            per_page=per_page,
        )
    
    # Get articles with pagination
    from sqlalchemy import func
    
    # Get total count
    count_query = select(func.count()).where(Article.id.in_(bookmarked_ids))
    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0
    
    # Get articles in bookmark order
    articles_query = (
        select(Article)
        .where(Article.id.in_(bookmarked_ids))
        .offset(offset)
        .limit(per_page)
    )
    articles_result = await db.execute(articles_query)
    articles = list(articles_result.scalars().all())
    
    # Convert to response format
    article_responses = []
    for article in articles:
        word_count = len(article.content.split()) if article.content else 0
        read_time = max(1, word_count // 200)
        
        article_responses.append(
            ArticleResponse(
                id=article.id,
                title=article.title,
                url=article.url,
                summary=article.summary,
                source=article.source,
                source_credibility_score=article.source_credibility_score,
                published_at=article.published_at,
                topic_tags=article.topic_tags,
                read_time_minutes=read_time,
                is_blind_spot=False,
            )
        )
    
    logger.info(
        "Retrieved bookmarks",
        user_id=str(user.id),
        count=len(article_responses),
    )
    
    has_more = offset + len(articles) < total_count
    
    return FeedResponse(
        articles=article_responses,
        has_more=has_more,
        total_count=total_count,
        page=page,
        per_page=per_page,
    )


@router.get("/{article_id}", response_model=ArticleDetailResponse)
async def get_article(
    article_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> ArticleDetailResponse:
    """
    Get full article details by ID.
    """
    result = await db.execute(
        select(Article).where(Article.id == article_id)
    )
    article = result.scalar_one_or_none()
    
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )
    
    word_count = len(article.content.split()) if article.content else 0
    read_time = max(1, word_count // 200)
    
    return ArticleDetailResponse(
        id=article.id,
        title=article.title,
        url=article.url,
        content=article.content,
        summary=article.summary,
        author=article.author,
        source=article.source,
        source_credibility_score=article.source_credibility_score,
        published_at=article.published_at,
        fetched_at=article.fetched_at,
        created_at=article.created_at,
        topic_tags=article.topic_tags,
        entity_mentions=article.entity_mentions,
        sentiment_score=article.sentiment_score,
        read_time_minutes=read_time,
    )
