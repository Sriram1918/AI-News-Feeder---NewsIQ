"""
User Embedding Update Tasks

Celery tasks for updating user personalization vectors.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List
from uuid import UUID

from celery import shared_task
from sqlalchemy import select

from app.config.logging import get_logger
from app.db import get_db_context
from app.models import User
from app.services.personalization import user_modeler

logger = get_logger(__name__)


def run_async(coro):
    """Run async function in sync context for Celery."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(bind=True)
def update_all_user_embeddings(self) -> dict:
    """
    Update long-term embeddings for all active users.
    
    Runs daily at 2 AM via Celery Beat.
    """
    return run_async(_update_all_embeddings_async())


async def _update_all_embeddings_async() -> dict:
    """Async implementation."""
    async with get_db_context() as db:
        # Get users active in last 30 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        
        result = await db.execute(
            select(User).where(
                User.is_active == True,
                User.last_active >= cutoff,
            )
        )
        users = list(result.scalars().all())
        
        logger.info("Updating user embeddings", user_count=len(users))
        
        updated = 0
        errors = 0
        
        for user in users:
            try:
                success = await user_modeler.update_user_long_term_vector(db, user.id)
                if success:
                    updated += 1
            except Exception as e:
                logger.error(
                    "Failed to update user embedding",
                    user_id=str(user.id),
                    error=str(e),
                )
                errors += 1
        
        logger.info(
            "User embedding update complete",
            updated=updated,
            errors=errors,
            total=len(users),
        )
        
        return {
            "total_users": len(users),
            "updated": updated,
            "errors": errors,
        }


@shared_task
def update_single_user_embedding(user_id: str) -> dict:
    """Update embedding for a single user."""
    return run_async(_update_single_user_async(UUID(user_id)))


async def _update_single_user_async(user_id: UUID) -> dict:
    """Async implementation."""
    async with get_db_context() as db:
        try:
            success = await user_modeler.update_user_long_term_vector(db, user_id)
            
            return {
                "user_id": str(user_id),
                "success": success,
            }
            
        except Exception as e:
            logger.error(
                "Failed to update user embedding",
                user_id=str(user_id),
                error=str(e),
            )
            
            return {
                "user_id": str(user_id),
                "success": False,
                "error": str(e),
            }
