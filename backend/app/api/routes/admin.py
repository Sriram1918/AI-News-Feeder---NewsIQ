"""
Admin API Routes

Endpoints for triggering background tasks manually or via external cron.
These endpoints replace the need for Celery/APScheduler.
"""

from fastapi import APIRouter, HTTPException, Header, status
from typing import Optional

from app.config.logging import get_logger
from app.config.settings import settings

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


# Simple auth for admin endpoints (optional - use a secret token)
async def verify_admin_token(x_admin_token: Optional[str] = Header(None)) -> bool:
    """
    Optional authentication for admin endpoints.
    Set ADMIN_TOKEN env var to enable protection.
    """
    admin_token = getattr(settings, 'admin_token', None)
    if admin_token and x_admin_token != admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token"
        )
    return True


@router.post("/fetch-feeds")
async def trigger_fetch_feeds():
    """
    Trigger RSS feed fetching.
    
    Call this endpoint every 5 minutes via cron-job.org to fetch new articles.
    
    Example cron-job.org setup:
    - URL: https://your-app.onrender.com/api/v1/admin/fetch-feeds
    - Method: POST
    - Schedule: Every 5 minutes
    """
    from app.tasks.fetch_feeds import _fetch_all_feeds_async
    
    try:
        logger.info("Manual feed fetch triggered")
        result = await _fetch_all_feeds_async()
        logger.info(
            "Feed fetch complete",
            articles=result.get("total_articles", 0),
            sources=result.get("sources_processed", 0),
        )
        return {
            "success": True,
            "message": "Feed fetch completed",
            **result
        }
    except Exception as e:
        logger.error("Feed fetch failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/update-embeddings")
async def trigger_update_embeddings():
    """
    Trigger user embedding updates.
    
    Call this daily via cron-job.org.
    """
    from app.tasks.update_embeddings import _update_all_embeddings_async
    
    try:
        logger.info("Manual embedding update triggered")
        result = await _update_all_embeddings_async()
        return {
            "success": True,
            "message": "Embedding update completed",
            **result
        }
    except Exception as e:
        logger.error("Embedding update failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/cluster-stories")
async def trigger_cluster_stories():
    """
    Trigger story clustering.
    
    Call this every 6 hours via cron-job.org.
    """
    from app.tasks.cluster_stories import _cluster_articles_async
    
    try:
        logger.info("Manual clustering triggered")
        result = await _cluster_articles_async()
        return {
            "success": True,
            "message": "Clustering completed",
            **result
        }
    except Exception as e:
        logger.error("Clustering failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/cleanup-cache")
async def trigger_cleanup_cache():
    """
    Trigger cache cleanup.
    
    Call this hourly via cron-job.org.
    """
    from app.tasks.fetch_feeds import _cleanup_cache_async
    
    try:
        logger.info("Manual cache cleanup triggered")
        result = await _cleanup_cache_async()
        return {
            "success": True,
            "message": "Cache cleanup completed",
            **result
        }
    except Exception as e:
        logger.error("Cache cleanup failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/status")
async def get_system_status():
    """
    Get system status - useful for health checks.
    """
    from app.db import get_db_context
    from sqlalchemy import select, func
    from app.models import Article, RSSSource, User
    
    try:
        async with get_db_context() as db:
            # Count articles
            result = await db.execute(select(func.count(Article.id)))
            article_count = result.scalar() or 0
            
            # Count sources
            result = await db.execute(select(func.count(RSSSource.id)))
            source_count = result.scalar() or 0
            
            # Count users
            result = await db.execute(select(func.count(User.id)))
            user_count = result.scalar() or 0
            
            return {
                "status": "healthy",
                "articles": article_count,
                "sources": source_count,
                "users": user_count,
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
