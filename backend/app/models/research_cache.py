"""
Research Cache Model

SQLAlchemy model for deep research caching.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    TIMESTAMP,
    Boolean,
    ForeignKey,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base


class ResearchCache(Base):
    """
    ResearchCache model for caching Deep Research analysis.
    
    Stores generated analysis results with TTL for performance.
    Invalidates when new related articles appear.
    """
    
    __tablename__ = "research_cache"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    
    # Foreign key
    article_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Cache content
    analysis_text: Mapped[str] = mapped_column(Text, nullable=False)
    related_article_ids: Mapped[Optional[List[UUID]]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)),
        nullable=True,
    )
    
    # Cache metadata
    generated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default="NOW()",
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalidated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relationships
    article: Mapped["Article"] = relationship("Article", back_populates="research_cache")
    
    def __repr__(self) -> str:
        return f"<ResearchCache(id={self.id}, article_id={self.article_id})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert cache entry to dictionary."""
        return {
            "id": str(self.id),
            "article_id": str(self.article_id),
            "analysis_text": self.analysis_text,
            "related_article_ids": [str(aid) for aid in (self.related_article_ids or [])],
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "view_count": self.view_count,
            "from_cache": True,
        }
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.now(timezone.utc) > self.expires_at or self.invalidated


# Import at bottom to avoid circular imports
from app.models.article import Article  # noqa: E402
