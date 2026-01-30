"""
APScheduler - Background Task Scheduler for Render Deployment

Replaces Celery with APScheduler for serverless/free-tier deployments.
Runs scheduled tasks within the FastAPI application lifecycle.

This module provides:
- RSS feed fetching every 5 minutes
- User embedding updates daily at 2 AM
- Story clustering every 6 hours
- Cache cleanup hourly
"""

import asyncio
from datetime import datetime, timezone
from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config.logging import get_logger

logger = get_logger(__name__)


class BackgroundScheduler:
    """
    Background task scheduler using APScheduler.
    
    Drop-in replacement for Celery Beat that runs within the FastAPI process.
    """
    
    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._is_running = False
    
    def start(self) -> None:
        """Start the scheduler with all configured jobs."""
        if self._is_running:
            logger.warning("Scheduler already running")
            return
        
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        
        # Register all scheduled tasks
        self._register_jobs()
        
        # Start the scheduler
        self.scheduler.start()
        self._is_running = True
        
        logger.info("Background scheduler started", jobs=len(self.scheduler.get_jobs()))
    
    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if self.scheduler and self._is_running:
            self.scheduler.shutdown(wait=True)
            self._is_running = False
            logger.info("Background scheduler stopped")
    
    def _register_jobs(self) -> None:
        """Register all background jobs."""
        
        # 1. Fetch RSS feeds every 5 minutes
        self.scheduler.add_job(
            self._fetch_feeds,
            trigger=IntervalTrigger(minutes=5),
            id="fetch_rss_feeds",
            name="Fetch RSS Feeds",
            replace_existing=True,
            max_instances=1,
        )
        
        # 2. Update user embeddings daily at 2 AM UTC
        self.scheduler.add_job(
            self._update_user_embeddings,
            trigger=CronTrigger(hour=2, minute=0),
            id="update_user_embeddings",
            name="Update User Embeddings",
            replace_existing=True,
            max_instances=1,
        )
        
        # 3. Cluster stories every 6 hours
        self.scheduler.add_job(
            self._cluster_stories,
            trigger=CronTrigger(hour="*/6", minute=0),
            id="cluster_stories",
            name="Cluster Stories",
            replace_existing=True,
            max_instances=1,
        )
        
        # 4. Cleanup expired cache every hour at :30
        self.scheduler.add_job(
            self._cleanup_cache,
            trigger=CronTrigger(minute=30),
            id="cleanup_cache",
            name="Cleanup Expired Cache",
            replace_existing=True,
            max_instances=1,
        )
        
        logger.info("Registered scheduled jobs", count=4)
    
    async def _fetch_feeds(self) -> None:
        """Fetch all RSS feeds - runs every 5 minutes."""
        from app.tasks.fetch_feeds import _fetch_all_feeds_async
        
        try:
            logger.info("Starting scheduled RSS fetch")
            result = await _fetch_all_feeds_async()
            logger.info(
                "Scheduled RSS fetch complete",
                articles=result.get("total_articles", 0),
                sources=result.get("sources_processed", 0),
            )
        except Exception as e:
            logger.error("Scheduled RSS fetch failed", error=str(e))
    
    async def _update_user_embeddings(self) -> None:
        """Update user embeddings - runs daily at 2 AM."""
        from app.tasks.update_embeddings import _update_all_embeddings_async
        
        try:
            logger.info("Starting scheduled user embedding update")
            result = await _update_all_embeddings_async()
            logger.info(
                "Scheduled embedding update complete",
                updated=result.get("updated", 0),
                total=result.get("total_users", 0),
            )
        except Exception as e:
            logger.error("Scheduled embedding update failed", error=str(e))
    
    async def _cluster_stories(self) -> None:
        """Cluster stories - runs every 6 hours."""
        from app.tasks.cluster_stories import _cluster_articles_async
        
        try:
            logger.info("Starting scheduled story clustering")
            result = await _cluster_articles_async()
            logger.info(
                "Scheduled clustering complete",
                created=result.get("clusters_created", 0),
                updated=result.get("clusters_updated", 0),
            )
        except Exception as e:
            logger.error("Scheduled clustering failed", error=str(e))
    
    async def _cleanup_cache(self) -> None:
        """Cleanup expired cache - runs hourly."""
        from app.tasks.fetch_feeds import _cleanup_cache_async
        
        try:
            logger.info("Starting scheduled cache cleanup")
            result = await _cleanup_cache_async()
            logger.info(
                "Scheduled cache cleanup complete",
                deleted=result.get("deleted_entries", 0),
            )
        except Exception as e:
            logger.error("Scheduled cache cleanup failed", error=str(e))
    
    async def run_task_now(self, task_name: str) -> dict:
        """
        Run a specific task immediately (on-demand).
        
        Useful for admin endpoints to trigger tasks manually.
        """
        tasks = {
            "fetch_feeds": self._fetch_feeds,
            "update_embeddings": self._update_user_embeddings,
            "cluster_stories": self._cluster_stories,
            "cleanup_cache": self._cleanup_cache,
        }
        
        if task_name not in tasks:
            return {"error": f"Unknown task: {task_name}", "available": list(tasks.keys())}
        
        try:
            await tasks[task_name]()
            return {"success": True, "task": task_name, "timestamp": datetime.now(timezone.utc).isoformat()}
        except Exception as e:
            return {"success": False, "task": task_name, "error": str(e)}
    
    def get_status(self) -> dict:
        """Get scheduler status and job information."""
        if not self.scheduler or not self._is_running:
            return {"running": False, "jobs": []}
        
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            })
        
        return {
            "running": True,
            "jobs": jobs,
            "job_count": len(jobs),
        }


# Singleton instance
background_scheduler = BackgroundScheduler()
