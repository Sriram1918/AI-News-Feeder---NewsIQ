"""
User Interaction Model

SQLAlchemy model for tracking user-article interactions.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base


class InteractionType(str, Enum):
    """Enum for interaction types."""
    VIEW = "view"
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"
    MUTE = "mute"
    BOOKMARK = "bookmark"
    DEEP_RESEARCH = "deep_research"


# Interaction weights for personalization algorithm
INTERACTION_WEIGHTS = {
    InteractionType.DEEP_RESEARCH: 5.0,
    InteractionType.BOOKMARK: 3.0,
    InteractionType.UPVOTE: 2.0,
    InteractionType.VIEW: 1.0,
    InteractionType.DOWNVOTE: -2.0,
    InteractionType.MUTE: -5.0,
}


class UserInteraction(Base):
    """
    UserInteraction model tracking user-article interactions.
    
    Used for:
    - Building user interest profiles
    - Personalization algorithm training
    - Engagement analytics
    """
    
    __tablename__ = "user_interactions"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    
    # Foreign keys
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    article_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Interaction details
    interaction_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    read_time_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scroll_depth_percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default="NOW()",
        index=True,
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="interactions")
    article: Mapped["Article"] = relationship("Article", back_populates="interactions")
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "scroll_depth_percent BETWEEN 0 AND 100",
            name="check_scroll_depth_range",
        ),
        CheckConstraint(
            "interaction_type IN ('view', 'upvote', 'downvote', 'mute', 'bookmark', 'deep_research')",
            name="check_interaction_type_valid",
        ),
    )
    
    def __repr__(self) -> str:
        return f"<UserInteraction(id={self.id}, type='{self.interaction_type}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert interaction to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "article_id": str(self.article_id),
            "interaction_type": self.interaction_type,
            "read_time_seconds": self.read_time_seconds,
            "scroll_depth_percent": self.scroll_depth_percent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    @property
    def weight(self) -> float:
        """Get the weight for this interaction type."""
        try:
            return INTERACTION_WEIGHTS[InteractionType(self.interaction_type)]
        except (ValueError, KeyError):
            return 0.0


# Import at bottom to avoid circular imports
from app.models.article import Article  # noqa: E402, F811
from app.models.user import User  # noqa: E402, F811
