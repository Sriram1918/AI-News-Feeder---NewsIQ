"""
Tasks Package.

Exports Celery tasks and app.
"""

from app.tasks.celery_app import celery_app
from app.tasks.cluster_stories import cluster_recent_articles
from app.tasks.fetch_feeds import (
    cleanup_expired_cache,
    fetch_all_feeds,
    fetch_single_source,
)
from app.tasks.update_embeddings import (
    update_all_user_embeddings,
    update_single_user_embedding,
)

__all__ = [
    "celery_app",
    "fetch_all_feeds",
    "fetch_single_source",
    "cleanup_expired_cache",
    "update_all_user_embeddings",
    "update_single_user_embedding",
    "cluster_recent_articles",
]
