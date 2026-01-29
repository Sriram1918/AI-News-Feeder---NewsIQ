"""
Story Cluster and Research Cache Models

SQLAlchemy models for story clustering and deep research caching.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    TIMESTAMP,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base


class StoryCluster(Base):
    """
    StoryCluster model for grouping related articles.
    
    Uses DBSCAN clustering on article embeddings to detect
    evolving story narratives over time.
    """
    
    __tablename__ = "story_clusters"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="uuid_generate_v4()",
    )
    
    # Cluster metadata
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default="developing",
        nullable=False,
    )
    
    # Tracking
    first_seen: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    article_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Cluster centroid for similarity matching
    centroid_embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(768),
        nullable=True,
    )
    
    __table_args__ = (
        Index(
            "idx_clusters_centroid",
            "centroid_embedding",
            postgresql_using="hnsw",
            postgresql_ops={"centroid_embedding": "vector_cosine_ops"},
        ),
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default="NOW()",
    )
    
    # Relationships
    article_associations: Mapped[List["ArticleCluster"]] = relationship(
        "ArticleCluster",
        back_populates="cluster",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<StoryCluster(id={self.id}, title='{self.title[:30]}...')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert cluster to dictionary."""
        return {
            "id": str(self.id),
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "article_count": self.article_count,
            "is_active": self.is_active,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


class ArticleCluster(Base):
    """
    ArticleCluster model for many-to-many article-cluster relationships.
    
    Tracks which articles belong to which story clusters,
    with relevance scores for ranking.
    """
    
    __tablename__ = "article_clusters"
    
    # Composite primary key
    article_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    cluster_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("story_clusters.id", ondelete="CASCADE"),
        primary_key=True,
    )
    
    # Metadata
    relevance_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default="NOW()",
    )
    
    # Relationships
    article: Mapped["Article"] = relationship("Article")
    cluster: Mapped["StoryCluster"] = relationship(
        "StoryCluster",
        back_populates="article_associations",
    )
    
    def __repr__(self) -> str:
        return f"<ArticleCluster(article={self.article_id}, cluster={self.cluster_id})>"


