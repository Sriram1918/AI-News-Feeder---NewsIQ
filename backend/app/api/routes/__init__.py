"""
API Routes Package.

Exports all API routers.
"""

from app.api.routes.admin import router as admin_router
from app.api.routes.feed import router as feed_router
from app.api.routes.research import router as research_router
from app.api.routes.stories import router as stories_router
from app.api.routes.user import router as user_router

__all__ = [
    "admin_router",
    "feed_router",
    "user_router",
    "research_router",
    "stories_router",
]

