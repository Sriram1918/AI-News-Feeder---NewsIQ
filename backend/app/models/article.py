"""
Article Model

SQLAlchemy model for news articles with pgvector embedding support.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    TIMESTAMP,
    CheckConstraint,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base


class Article(Base):
    """
    Article model representing a news article.
    
    Stores article content, metadata, embeddings, and extracted entities.
    Uses pgvector for efficient similarity search on embeddings.
    """
    
    __tablename__ = "articles"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    
    # Core content
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Source information
    source: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_credibility_score: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    # Timestamps
    published_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default="NOW()",
    )
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
    
    # Vector embedding for semantic search (768 dimensions for Google Gemini)
    # Note: Vector dimensions must match the embedding model
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(768),
        nullable=True,
    )
    
    # Metadata
    topic_tags: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(Text),
        nullable=True,
        default=list,
    )
    entity_mentions: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )
    sentiment_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    
    # Relationships
    interactions: Mapped[List["UserInteraction"]] = relationship(
        "UserInteraction",
        back_populates="article",
        cascade="all, delete-orphan",
    )
    research_cache: Mapped[List["ResearchCache"]] = relationship(
        "ResearchCache",
        back_populates="article",
        cascade="all, delete-orphan",
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "source_credibility_score BETWEEN 0 AND 100",
            name="check_credibility_score_range",
        ),
        CheckConstraint(
            "sentiment_score BETWEEN -1 AND 1",
            name="check_sentiment_score_range",
        ),
        Index(
            "idx_articles_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    
    def __repr__(self) -> str:
        return f"<Article(id={self.id}, title='{self.title[:50]}...', source='{self.source}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert article to dictionary for API responses."""
        return {
            "id": str(self.id),
            "url": self.url,
            "title": self.title,
            "summary": self.summary,
            "author": self.author,
            "source": self.source,
            "source_credibility_score": self.source_credibility_score,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "topic_tags": self.topic_tags or [],
            "sentiment_score": self.sentiment_score,
        }


# Import at bottom to avoid circular imports
from app.models.interaction import UserInteraction  # noqa: E402
from app.models.research_cache import ResearchCache  # noqa: E402
