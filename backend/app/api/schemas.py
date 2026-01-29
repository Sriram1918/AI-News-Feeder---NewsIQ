"""
Pydantic Schemas for API Request/Response Models

Following official Pydantic V2 documentation:
https://docs.pydantic.dev/latest/
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# =============================================================================
# Enums
# =============================================================================

class InteractionTypeEnum(str, Enum):
    """Interaction types for user-article interactions."""
    VIEW = "view"
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"
    MUTE = "mute"
    BOOKMARK = "bookmark"
    DEEP_RESEARCH = "deep_research"


class DiversityLevelEnum(str, Enum):
    """Diversity level settings for personalization."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StoryStatusEnum(str, Enum):
    """Status of a story cluster."""
    DEVELOPING = "developing"
    ONGOING = "ongoing"
    RESOLVED = "resolved"


# =============================================================================
# Base Schemas
# =============================================================================

class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    
    model_config = ConfigDict(
        from_attributes=True,  # Enable ORM mode
        populate_by_name=True,
        use_enum_values=True,
    )


# =============================================================================
# Article Schemas
# =============================================================================

class ArticleBase(BaseSchema):
    """Base article schema with common fields."""
    title: str = Field(..., min_length=1, max_length=500)
    url: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1, max_length=255)


class ArticleCreate(ArticleBase):
    """Schema for creating a new article."""
    content: str = Field(..., min_length=1)
    summary: Optional[str] = None
    author: Optional[str] = None
    published_at: datetime
    source_credibility_score: Optional[int] = Field(None, ge=0, le=100)
    topic_tags: Optional[List[str]] = None


class ArticleResponse(ArticleBase):
    """Schema for article API responses."""
    id: UUID
    summary: Optional[str] = None
    author: Optional[str] = None
    source_credibility_score: Optional[int] = None
    published_at: datetime
    topic_tags: Optional[List[str]] = None
    sentiment_score: Optional[float] = None
    relevance_score: Optional[float] = None
    is_blind_spot: bool = False
    read_time_minutes: Optional[int] = None
    thumbnail_url: Optional[str] = None


class ArticleDetailResponse(ArticleResponse):
    """Detailed article response with full content."""
    content: str
    entity_mentions: Optional[Dict[str, Any]] = None
    fetched_at: datetime
    created_at: datetime


# =============================================================================
# Feed Schemas
# =============================================================================

class FeedResponse(BaseSchema):
    """Schema for paginated feed response."""
    articles: List[ArticleResponse]
    has_more: bool
    total_count: int
    page: int
    per_page: int


class FeedQueryParams(BaseSchema):
    """Query parameters for feed endpoint."""
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=50)
    include_blind_spots: bool = True


# =============================================================================
# User Schemas
# =============================================================================

class UserBase(BaseSchema):
    """Base user schema."""
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=8, max_length=100)
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Ensure password meets security requirements."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserResponse(UserBase):
    """Schema for user API responses."""
    id: UUID
    is_active: bool
    is_verified: bool
    onboarding_completed: bool
    preference_topics: List[str] = []
    muted_sources: List[str] = []
    diversity_level: DiversityLevelEnum = DiversityLevelEnum.MEDIUM
    created_at: datetime


class UserPreferencesUpdate(BaseSchema):
    """Schema for updating user preferences."""
    topics: Optional[List[str]] = None
    muted_sources: Optional[List[str]] = None
    diversity_level: Optional[DiversityLevelEnum] = None


# =============================================================================
# Authentication Schemas
# =============================================================================

class TokenResponse(BaseSchema):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseSchema):
    """Schema for JWT token payload."""
    sub: str  # User ID
    exp: datetime


class LoginRequest(BaseSchema):
    """Schema for login request."""
    email: EmailStr
    password: str


# =============================================================================
# Interaction Schemas
# =============================================================================

class InteractionCreate(BaseSchema):
    """Schema for creating a user interaction."""
    article_id: UUID
    type: InteractionTypeEnum = Field(..., alias="interaction_type")
    read_time_seconds: Optional[int] = Field(None, ge=0)
    scroll_depth: Optional[int] = Field(None, ge=0, le=100)
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
    )


class InteractionResponse(BaseSchema):
    """Schema for interaction API responses."""
    success: bool
    feed_updated: bool
    message: Optional[str] = None


# =============================================================================
# Deep Research Schemas
# =============================================================================

class ResearchRequest(BaseSchema):
    """Schema for deep research request."""
    article_id: UUID


class RelatedArticle(BaseSchema):
    """Schema for related article in research response."""
    id: UUID
    title: str
    url: str
    source: str
    published_at: datetime


class ResearchResponse(BaseSchema):
    """Schema for deep research API response."""
    analysis: str  # Markdown formatted analysis
    related_articles: List[RelatedArticle]
    generated_at: datetime
    from_cache: bool


# =============================================================================
# Story Timeline Schemas
# =============================================================================

class TimelineEvent(BaseSchema):
    """Schema for a single timeline event."""
    date: str  # ISO date string
    event: str
    article_count: int
    key_articles: List[ArticleResponse]


class TimelineResponse(BaseSchema):
    """Schema for story timeline API response."""
    cluster_id: UUID
    title: str
    description: Optional[str] = None
    status: StoryStatusEnum
    timeline: List[TimelineEvent]
    current_status: str
    total_articles: int
    first_seen: datetime
    last_updated: datetime


class StoryClusterResponse(BaseSchema):
    """Schema for story cluster list response."""
    id: UUID
    title: str
    description: Optional[str] = None
    status: StoryStatusEnum
    article_count: int
    is_active: bool
    first_seen: datetime
    last_updated: datetime


# =============================================================================
# Onboarding Schemas
# =============================================================================

class OnboardingTopicSelection(BaseSchema):
    """Schema for onboarding topic selection."""
    topics: List[str] = Field(..., min_length=1, max_length=10)


class OnboardingArticleSelection(BaseSchema):
    """Schema for onboarding article selection."""
    article_ids: List[UUID] = Field(..., min_length=1, max_length=10)


class OnboardingComplete(BaseSchema):
    """Response for completed onboarding."""
    success: bool
    message: str
    user: UserResponse


# =============================================================================
# Error Schemas
# =============================================================================

class ErrorResponse(BaseSchema):
    """Schema for error responses."""
    detail: str
    error_code: Optional[str] = None


class ValidationErrorDetail(BaseSchema):
    """Schema for validation error details."""
    loc: List[str]
    msg: str
    type: str


class ValidationErrorResponse(BaseSchema):
    """Schema for validation error response."""
    detail: List[ValidationErrorDetail]
