"""
Rate Limiting Middleware

Implements rate limiting using Redis.
"""

import time
from typing import Optional

import redis.asyncio as redis
from fastapi import HTTPException, Request, status

from app.config.logging import get_logger
from app.config.settings import settings

logger = get_logger(__name__)


class RateLimiter:
    """
    Rate limiter using Redis sliding window.
    
    Features:
    - Per-IP and per-user rate limiting
    - Configurable limits per endpoint
    - Sliding window algorithm
    """
    
    def __init__(self):
        """Initialize the rate limiter."""
        self.redis: Optional[redis.Redis] = None
        self.default_limit = settings.rate_limit_per_minute
        self.window_seconds = 20
    
    async def connect(self) -> None:
        """Connect to Redis."""
        if self.redis is None:
            self.redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("Rate limiter connected to Redis")
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            self.redis = None
    
    def _get_key(
        self,
        identifier: str,
        endpoint: str,
    ) -> str:
        """Generate Redis key for rate limit."""
        return f"ratelimit:{endpoint}:{identifier}"
    
    async def is_allowed(
        self,
        identifier: str,
        endpoint: str = "default",
        limit: Optional[int] = None,
    ) -> tuple[bool, int, int]:
        """
        Check if request is allowed under rate limit.
        
        Args:
            identifier: User ID or IP address.
            endpoint: Endpoint identifier.
            limit: Custom limit (defaults to global limit).
            
        Returns:
            Tuple of (is_allowed, remaining, reset_time).
        """
        if self.redis is None:
            await self.connect()
        
        limit = limit or self.default_limit
        key = self._get_key(identifier, endpoint)
        now = time.time()
        window_start = now - self.window_seconds
        
        pipe = self.redis.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        # Count current entries
        pipe.zcard(key)
        # Add current request
        pipe.zadd(key, {str(now): now})
        # Set expiry
        pipe.expire(key, self.window_seconds)
        
        results = await pipe.execute()
        current_count = results[1]
        
        remaining = max(0, limit - current_count - 1)
        reset_time = int(now + self.window_seconds)
        
        is_allowed = current_count < limit
        
        if not is_allowed:
            logger.warning(
                "Rate limit exceeded",
                identifier=identifier,
                endpoint=endpoint,
                limit=limit,
            )
        
        return is_allowed, remaining, reset_time
    
    async def check_rate_limit(
        self,
        request: Request,
        limit: Optional[int] = None,
        endpoint: Optional[str] = None,
    ) -> None:
        """
        Check rate limit and raise exception if exceeded.
        
        Args:
            request: FastAPI request object.
            limit: Custom limit.
            endpoint: Custom endpoint identifier.
            
        Raises:
            HTTPException: If rate limit exceeded.
        """
        # Get identifier (user ID from state or client IP)
        user = getattr(request.state, "user", None)
        if user:
            identifier = str(user.id)
        else:
            # Use client IP
            identifier = request.client.host if request.client else "unknown"
        
        endpoint = endpoint or request.url.path
        
        is_allowed, remaining, reset_time = await self.is_allowed(
            identifier=identifier,
            endpoint=endpoint,
            limit=limit,
        )
        
        if not is_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={
                    "X-RateLimit-Limit": str(limit or self.default_limit),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(self.window_seconds),
                },
            )


# Singleton instance
rate_limiter = RateLimiter()
