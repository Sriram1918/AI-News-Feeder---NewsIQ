"""
FastAPI Main Application

Entry point for the News Intelligence System API.
Following official FastAPI documentation:
https://fastapi.tiangolo.com/
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import admin_router, feed_router, research_router, stories_router, user_router
from app.api.middleware import rate_limiter
from app.config.logging import get_logger, setup_logging
from app.config.settings import settings
from app.db import close_db

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events:
    - Connect to Redis for rate limiting
    - Initialize database connections
    - Cleanup on shutdown
    """
    # Startup
    logger.info(
        "Starting News Intelligence System",
        environment=settings.app_env,
        debug=settings.debug,
    )
    
    # Connect rate limiter to Redis
    try:
        await rate_limiter.connect()
        logger.info("Rate limiter connected to Redis")
    except Exception as e:
        logger.warning("Failed to connect rate limiter", error=str(e))
    
    yield
    
    # Shutdown
    logger.info("Shutting down News Intelligence System")
    
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
    Health check endpoint.
    
    Returns system status and basic metrics.
    """
    return {
        "status": "healthy",
        "environment": settings.app_env,
        "version": "1.0.0",
    }


# API v1 routers
app.include_router(admin_router, prefix="/api/v1")
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
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
