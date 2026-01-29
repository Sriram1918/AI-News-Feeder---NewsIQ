"""
Story Timeline API Routes

Endpoints for story clusters and timelines.
"""

from datetime import datetime, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    ArticleResponse,
    StoryClusterResponse,
    TimelineEvent,
    TimelineResponse,
)
from app.config.logging import get_logger
from app.db import get_db_session
from app.models import Article, ArticleCluster, StoryCluster

logger = get_logger(__name__)

router = APIRouter(prefix="/stories", tags=["Stories"])


@router.get("", response_model=List[StoryClusterResponse])
async def list_story_clusters(
    active_only: bool = Query(default=True, description="Only show active stories"),
    limit: int = Query(default=20, ge=1, le=100, description="Max results"),
    db: AsyncSession = Depends(get_db_session),
) -> List[StoryClusterResponse]:
    """
    List all story clusters.
    
    Returns evolving story narratives grouped by topic.
    """
    query = select(StoryCluster).order_by(StoryCluster.last_updated.desc())
    
    if active_only:
        query = query.where(StoryCluster.is_active == True)
    
    query = query.limit(limit)
    
    result = await db.execute(query)
    clusters = result.scalars().all()
    
    return [
        StoryClusterResponse(
            id=c.id,
            title=c.title,
            description=c.description,
            status=c.status,
            article_count=c.article_count,
            is_active=c.is_active,
            first_seen=c.first_seen,
            last_updated=c.last_updated,
        )
        for c in clusters
    ]


@router.get("/{cluster_id}", response_model=TimelineResponse)
async def get_story_timeline(
    cluster_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> TimelineResponse:
    """
    Get timeline for a story cluster.
    
    Returns chronological events with key articles.
    """
    # Fetch cluster
    result = await db.execute(
        select(StoryCluster).where(StoryCluster.id == cluster_id)
    )
    cluster = result.scalar_one_or_none()
    
    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story cluster not found",
        )
    
    # Fetch articles in cluster
    query = (
        select(Article)
        .join(ArticleCluster, ArticleCluster.article_id == Article.id)
        .where(ArticleCluster.cluster_id == cluster_id)
        .order_by(Article.published_at.asc())
    )
    
    result = await db.execute(query)
    articles = list(result.scalars().all())
    
    # Group articles by date
    date_groups = {}
    for article in articles:
        date_str = article.published_at.strftime("%Y-%m-%d")
        if date_str not in date_groups:
            date_groups[date_str] = []
        date_groups[date_str].append(article)
    
    # Build timeline events
    timeline = []
    for date_str, day_articles in sorted(date_groups.items()):
        # Get most significant article for the day (by read time proxy)
        day_articles.sort(key=lambda a: len(a.content) if a.content else 0, reverse=True)
        
        # Create event summary (simplified - could use LLM in production)
        top_article = day_articles[0]
        event_summary = top_article.title
        
        # Convert articles to response format
        key_articles = []
        for article in day_articles[:3]:  # Top 3 per day
            word_count = len(article.content.split()) if article.content else 0
            read_time = max(1, word_count // 200)
            
            key_articles.append(
                ArticleResponse(
                    id=article.id,
                    title=article.title,
                    url=article.url,
                    summary=article.summary,
                    author=article.author,
                    source=article.source,
                    source_credibility_score=article.source_credibility_score,
                    published_at=article.published_at,
                    read_time_minutes=read_time,
                )
            )
        
        timeline.append(
            TimelineEvent(
                date=date_str,
                event=event_summary,
                article_count=len(day_articles),
                key_articles=key_articles,
            )
        )
    
    # Generate current status
    status_map = {
        "developing": "Story is developing - new information expected",
        "ongoing": "Ongoing coverage continues",
        "resolved": "Story has concluded",
    }
    current_status = status_map.get(cluster.status, "Status unknown")
    
    logger.info(
        "Retrieved story timeline",
        cluster_id=str(cluster_id),
        timeline_events=len(timeline),
    )
    
    return TimelineResponse(
        cluster_id=cluster.id,
        title=cluster.title,
        description=cluster.description,
        status=cluster.status,
        timeline=timeline,
        current_status=current_status,
        total_articles=cluster.article_count,
        first_seen=cluster.first_seen,
        last_updated=cluster.last_updated,
    )
