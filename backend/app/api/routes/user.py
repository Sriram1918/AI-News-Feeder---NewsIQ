"""
User API Routes

Endpoints for user management and authentication.
"""

from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.api.schemas import (
    InteractionCreate,
    InteractionResponse,
    LoginRequest,
    OnboardingArticleSelection,
    OnboardingComplete,
    OnboardingTopicSelection,
    TokenResponse,
    UserCreate,
    UserPreferencesUpdate,
    UserResponse,
)
from app.config.logging import get_logger
from app.config.settings import settings
from app.db import get_db_session
from app.models import Article, User, UserInteraction
from app.services.personalization import user_modeler

logger = get_logger(__name__)

router = APIRouter(prefix="/user", tags=["User"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """
    Register a new user.
    """
    # Check if email already exists
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Create user
    hashed_password = get_password_hash(user_data.password)
    
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    logger.info("User registered", user_id=str(user.id), email=user.email)
    
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """
    Authenticate user and return JWT token.
    """
    # Find user
    result = await db.execute(
        select(User).where(User.email == credentials.email)
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    
    # Create access token
    access_token = create_access_token(user.id)
    
    logger.info("User logged in", user_id=str(user.id))
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Get current authenticated user's profile.
    """
    return UserResponse.model_validate(user)


@router.post("/preferences", response_model=UserResponse)
async def update_preferences(
    preferences: UserPreferencesUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """
    Update user preferences.
    """
    if preferences.topics is not None:
        user.preference_topics = preferences.topics
    
    if preferences.muted_sources is not None:
        user.muted_sources = preferences.muted_sources
    
    if preferences.diversity_level is not None:
        user.diversity_level = preferences.diversity_level.value
    
    await db.commit()
    await db.refresh(user)
    
    logger.info("User preferences updated", user_id=str(user.id))
    
    return UserResponse.model_validate(user)


@router.post("/interactions", response_model=InteractionResponse)
async def record_interaction(
    interaction: InteractionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> InteractionResponse:
    """
    Record a user interaction with an article.
    
    Used for:
    - View tracking
    - Upvote/downvote
    - Bookmark
    - Mute (hide similar articles)
    - Deep Research usage
    """
    # Verify article exists
    result = await db.execute(
        select(Article).where(Article.id == interaction.article_id)
    )
    article = result.scalar_one_or_none()
    
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )
    
    # Create interaction
    user_interaction = UserInteraction(
        user_id=user.id,
        article_id=interaction.article_id,
        interaction_type=interaction.type,
        read_time_seconds=interaction.read_time_seconds,
        scroll_depth_percent=interaction.scroll_depth,
    )
    
    db.add(user_interaction)
    await db.commit()
    
    logger.info(
        "Interaction recorded",
        user_id=str(user.id),
        article_id=str(interaction.article_id),
        type=interaction.type,
    )
    
    # Feed will be updated on next request
    return InteractionResponse(
        success=True,
        feed_updated=True,
        message=f"Recorded {interaction.type} interaction",
    )


@router.post("/onboarding/topics", response_model=dict)
async def onboarding_select_topics(
    selection: OnboardingTopicSelection,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Step 1 of onboarding: Select topics of interest.
    """
    user.preference_topics = selection.topics
    await db.commit()
    
    logger.info(
        "Onboarding topics selected",
        user_id=str(user.id),
        topics=selection.topics,
    )
    
    return {
        "success": True,
        "message": f"Selected {len(selection.topics)} topics",
        "topics": selection.topics,
    }


@router.post("/onboarding/articles", response_model=OnboardingComplete)
async def onboarding_select_articles(
    selection: OnboardingArticleSelection,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> OnboardingComplete:
    """
    Step 2 of onboarding: Select articles to bootstrap preferences.
    
    This completes onboarding and generates initial user vector.
    """
    # Create upvote interactions for selected articles
    for article_id in selection.article_ids:
        interaction = UserInteraction(
            user_id=user.id,
            article_id=article_id,
            interaction_type="upvote",
        )
        db.add(interaction)
    
    # Calculate initial user vector
    await db.commit()
    
    await user_modeler.update_user_long_term_vector(db, user.id)
    
    # Mark onboarding complete
    user.onboarding_completed = True
    await db.commit()
    await db.refresh(user)
    
    logger.info(
        "Onboarding completed",
        user_id=str(user.id),
        articles_selected=len(selection.article_ids),
    )
    
    return OnboardingComplete(
        success=True,
        message="Onboarding completed! Your personalized feed is ready.",
        user=UserResponse.model_validate(user),
    )
