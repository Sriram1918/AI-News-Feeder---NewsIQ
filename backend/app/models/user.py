"""
User Model

SQLAlchemy model for users with personalization embeddings.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, TIMESTAMP, Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base


class User(Base):
    """
    User model representing a registered user.
    
    Stores authentication info, preferences, and personalization vectors.
    Uses pgvector for user interest embeddings.
    """
    
    __tablename__ = "users"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    
    # Authentication
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Profile
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
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
    last_active: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    # Personalization - long-term interest vector
    long_term_embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(768),
        nullable=True,
    )
    
    # Preferences
    preference_topics: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(Text),
        nullable=True,
        default=list,
    )
    muted_sources: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(Text),
        nullable=True,
        default=list,
    )
    diversity_level: Mapped[str] = mapped_column(
        String(20),
        default="medium",
        nullable=False,
    )
    
    # Relationships
    interactions: Mapped[List["UserInteraction"]] = relationship(
        "UserInteraction",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    session_vectors: Mapped[List["SessionVector"]] = relationship(
        "SessionVector",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary for API responses."""
        return {
            "id": str(self.id),
            "email": self.email,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "onboarding_completed": self.onboarding_completed,
            "preference_topics": self.preference_topics or [],
            "muted_sources": self.muted_sources or [],
            "diversity_level": self.diversity_level,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SessionVector(Base):
    """
    Session-based user preference vector.
    
    Stores temporary interest vectors based on recent interactions.
    Updated in real-time as users interact with articles.
    """
    
    __tablename__ = "session_vectors"
    
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(768),
        nullable=True,
    )
    interaction_count: Mapped[int] = mapped_column(default=0, nullable=False)
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
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="session_vectors")
    
    def __repr__(self) -> str:
        return f"<SessionVector(id={self.id}, user_id={self.user_id})>"


# Import at bottom to avoid circular imports
from app.models.interaction import UserInteraction  # noqa: E402
