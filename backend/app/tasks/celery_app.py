"""
Celery Application Configuration

Background task queue using Celery with Redis broker.
Following official Celery documentation:
https://docs.celeryq.dev/en/stable/
"""

from celery import Celery
from celery.schedules import crontab

from app.config.settings import settings

# Create Celery application
celery_app = Celery(
    "news_intelligence",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.fetch_feeds",
        "app.tasks.update_embeddings",
        "app.tasks.cluster_stories",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    
    # Result settings
    result_expires=3600,  # 1 hour
    
    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    
    # Concurrency
    worker_concurrency=2,
)

# Celery Beat schedule (periodic tasks)
celery_app.conf.beat_schedule = {
    # Fetch RSS feeds every 5 minutes
    "fetch-rss-feeds": {
        "task": "app.tasks.fetch_feeds.fetch_all_feeds",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
        "options": {"queue": "default"},
    },
    
    # Update user embeddings daily at 2 AM
    "update-user-embeddings": {
        "task": "app.tasks.update_embeddings.update_all_user_embeddings",
        "schedule": crontab(hour=2, minute=0),  # 2:00 AM daily
        "options": {"queue": "default"},
    },
    
    # Cluster stories every 6 hours
    "cluster-stories": {
        "task": "app.tasks.cluster_stories.cluster_recent_articles",
        "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
        "options": {"queue": "default"},
    },
    
    # Clean expired research cache every hour
    "cleanup-cache": {
        "task": "app.tasks.fetch_feeds.cleanup_expired_cache",
        "schedule": crontab(minute=30),  # Every hour at :30
        "options": {"queue": "default"},
    },
}

# Task routes
celery_app.conf.task_routes = {
    "app.tasks.fetch_feeds.*": {"queue": "default"},
    "app.tasks.update_embeddings.*": {"queue": "default"},
    "app.tasks.cluster_stories.*": {"queue": "default"},
}
