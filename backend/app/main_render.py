"""
FastAPI Main Application - Render Deployment Version

Entry point for the News Intelligence System API with APScheduler.
Use this for Render deployment instead of main.py.

Key Differences from main.py:
- Uses APScheduler instead of Celery for background tasks
- Scheduler runs within the FastAPI process
- No dependency on Redis for task queue (only for rate limiting/caching)
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import feed_router, research_router, stories_router, user_router
from app.api.middleware import rate_limiter
from app.config.logging import get_logger, setup_logging
from app.config.settings import settings
from app.db import close_db
from app.scheduler import background_scheduler

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager with APScheduler.
    
    Handles startup and shutdown events:
    - Connect to Redis for rate limiting (optional)
    - Start background scheduler
    - Initialize database connections
    - Cleanup on shutdown
    """
    # Startup
    logger.info(
        "Starting News Intelligence System (Render)",
        environment=settings.app_env,
        debug=settings.debug,
    )
    
    # Connect rate limiter to Redis (optional - graceful fallback)
    try:
        await rate_limiter.connect()
        logger.info("Rate limiter connected to Redis")
    except Exception as e:
        logger.warning("Rate limiter not connected (Redis unavailable)", error=str(e))
    
    # Start background scheduler
    try:
        background_scheduler.start()
        logger.info("Background scheduler started")
    except Exception as e:
        logger.error("Failed to start background scheduler", error=str(e))
    
    yield
    
    # Shutdown
    logger.info("Shutting down News Intelligence System")
    
    # Stop scheduler
    background_scheduler.stop()
    
    # Disconnect rate limiter
    await rate_limiter.disconnect()
    
    # Close database connections
    await close_db()


# Create FastAPI application
app = FastAPI(
    title="News Intelligence System",
    description="""
    AI-powered news aggregation and intelligence system.
    
    ## Features
    - **Personalized Feed**: News ranked by your interests
    - **Deep Research**: Get context and multiple perspectives on any article
    - **Story Timelines**: Track how stories evolve over time
    - **Ethical Diversity**: Combat filter bubbles with blind spot articles
    
    ## Authentication
    Most endpoints require JWT authentication. 
    Register at `/api/v1/user/register` and login at `/api/v1/user/login`.
    
    ## Deployment
    This instance uses APScheduler for background tasks (Render-optimized).
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS configuration - explicitly include all origins
cors_origins = settings.cors_origins.copy() if settings.cors_origins else []
# Always include these origins for production
production_origins = [
    "https://newsiq-frontend.onrender.com",
    "http://localhost:5173",
    "http://localhost:3000",
]
for origin in production_origins:
    if origin not in cors_origins:
        cors_origins.append(origin)

logger.info(f"CORS Origins configured: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred. Please try again later.",
            "error_code": "INTERNAL_ERROR",
        },
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    Health check endpoint with scheduler status.
    
    Returns system status and scheduler information.
    """
    scheduler_status = background_scheduler.get_status()
    
    return {
        "status": "healthy",
        "environment": settings.app_env,
        "version": "1.0.0",
        "deployment": "render",
        "scheduler": scheduler_status,
    }


# Scheduler admin endpoints
@app.get("/admin/scheduler/status", tags=["Admin"])
async def scheduler_status() -> dict:
    """Get background scheduler status and job information."""
    return background_scheduler.get_status()


@app.post("/admin/scheduler/run/{task_name}", tags=["Admin"])
async def run_task(task_name: str) -> dict:
    """
    Manually trigger a background task.
    
    Available tasks:
    - fetch_feeds: Fetch all RSS feeds
    - update_embeddings: Update user embeddings
    - cluster_stories: Cluster articles into stories
    - cleanup_cache: Clean expired cache entries
    """
    return await background_scheduler.run_task_now(task_name)


# API v1 routers
app.include_router(feed_router, prefix="/api/v1")
app.include_router(user_router, prefix="/api/v1")
app.include_router(research_router, prefix="/api/v1")
app.include_router(stories_router, prefix="/api/v1")


# Root redirect to docs
@app.get("/", include_in_schema=False)
async def root() -> dict:
    """Redirect to API documentation."""
    return {
        "message": "Welcome to News Intelligence System API",
        "docs": "/docs",
        "version": "1.0.0",
        "deployment": "render",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main_render:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
