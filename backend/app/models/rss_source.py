"""
RSS Source Model

SQLAlchemy model for managing RSS feed sources.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import TIMESTAMP, Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.connection import Base


class RSSSource(Base):
    """
    RSSSource model for managing RSS feed subscriptions.
    
    Tracks feed URLs, polling schedules, and fetch status.
    """
    
    __tablename__ = "rss_sources"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    
    # Feed details
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    credibility_score: Mapped[int] = mapped_column(Integer, default=70, nullable=False)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Fetch tracking
    last_fetched: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_successful_fetch: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    fetch_interval_minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    
    # Error tracking
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default="NOW()",
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default="NOW()",
        onupdate=lambda: datetime.now(timezone.utc),
    )
    
    def __repr__(self) -> str:
        return f"<RSSSource(id={self.id}, name='{self.name}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert source to dictionary."""
        return {
            "id": str(self.id),
            "url": self.url,
            "name": self.name,
            "category": self.category,
            "credibility_score": self.credibility_score,
            "is_active": self.is_active,
            "last_fetched": self.last_fetched.isoformat() if self.last_fetched else None,
            "fetch_interval_minutes": self.fetch_interval_minutes,
            "error_count": self.error_count,
        }
    
    def mark_success(self) -> None:
        """Mark a successful fetch."""
        self.last_fetched = datetime.now(timezone.utc)
        self.last_successful_fetch = datetime.now(timezone.utc)
        self.error_count = 0
        self.last_error = None
    
    def mark_failure(self, error: str) -> None:
        """Mark a failed fetch."""
        self.last_fetched = datetime.now(timezone.utc)
        self.error_count += 1
        self.last_error = error
        
        # Disable source after 10 consecutive failures
        if self.error_count >= 10:
            self.is_active = False
