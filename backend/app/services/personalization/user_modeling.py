"""
User Modeling Service

Calculates user interest embeddings from interaction history.
Implements the personalization algorithm from the specification.
"""

import math
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.logging import get_logger
from app.config.settings import settings
from app.models import Article, User, UserInteraction, INTERACTION_WEIGHTS, InteractionType

logger = get_logger(__name__)


class UserModeler:
    """
    User Modeling Service.
    
    Calculates user interest vectors from interaction history using:
    - Weighted interaction signals (Deep Research > Bookmark > Upvote, etc.)
    - Time decay (older interactions matter less)
    - Session-based real-time updates
    """
    
    def __init__(self):
        """Initialize the user modeler."""
        self.long_term_weight = settings.long_term_weight  # 0.7
        self.session_weight = settings.session_weight  # 0.3
        self.time_decay_days = 30  # Half-life for time decay
        self.dimensions = settings.embedding_dimensions
    
    def _calculate_time_decay(self, created_at: datetime, half_life_days: int = 30) -> float:
        """
        Calculate time decay weight using exponential decay.
        
        Args:
            created_at: When the interaction occurred.
            half_life_days: Days until weight is halved.
            
        Returns:
            Decay weight between 0 and 1.
        """
        now = datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        
        days_ago = (now - created_at).days
        # Exponential decay: e^(-days/half_life)
        return math.exp(-days_ago / half_life_days)
    
    def _get_interaction_weight(self, interaction_type: str) -> float:
        """Get the weight for an interaction type."""
        try:
            return INTERACTION_WEIGHTS[InteractionType(interaction_type)]
        except (ValueError, KeyError):
            return 1.0
    
    async def calculate_user_vector(
        self,
        db: AsyncSession,
        user_id: UUID,
        days_lookback: int = 30,
    ) -> Optional[List[float]]:
        """
        Calculate user interest embedding from interaction history.
        
        Args:
            db: Database session.
            user_id: User ID.
            days_lookback: How many days of history to use.
            
        Returns:
            User interest vector or None if insufficient data.
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_lookback)
        
        # Fetch interactions with article embeddings
        query = (
            select(UserInteraction, Article.embedding)
            .join(Article, UserInteraction.article_id == Article.id)
            .where(
                UserInteraction.user_id == user_id,
                UserInteraction.created_at >= cutoff_date,
                Article.embedding.isnot(None),
            )
            .order_by(UserInteraction.created_at.desc())
        )
        
        result = await db.execute(query)
        interactions = result.all()
        
        if not interactions:
            logger.debug("No interactions found for user", user_id=str(user_id))
            return None
        
        weighted_embeddings = []
        weights = []
        
        for interaction, embedding in interactions:
            if embedding is None:
                continue
            
            # Calculate weight
            interaction_weight = self._get_interaction_weight(interaction.interaction_type)
            time_weight = self._calculate_time_decay(interaction.created_at, self.time_decay_days)
            
            # Add read time boost for views
            read_time_boost = 1.0
            if (
                interaction.interaction_type == "view"
                and interaction.read_time_seconds
                and interaction.read_time_seconds > 30
            ):
                # Boost for articles read for >30 seconds
                read_time_boost = 1.5
            
            final_weight = interaction_weight * time_weight * read_time_boost
            
            # Convert embedding to numpy array
            if isinstance(embedding, list):
                emb_array = np.array(embedding)
            else:
                emb_array = np.array(embedding.tolist())
            
            weighted_embeddings.append(emb_array)
            weights.append(final_weight)
        
        if not weighted_embeddings:
            return None
        
        # Calculate weighted average
        embeddings_array = np.array(weighted_embeddings)
        weights_array = np.array(weights)
        
        # Normalize weights
        weights_array = weights_array / (np.abs(weights_array).sum() + 1e-10)
        
        # Weighted average
        user_vector = np.average(embeddings_array, axis=0, weights=weights_array)
        
        # L2 normalize
        norm = np.linalg.norm(user_vector)
        if norm > 0:
            user_vector = user_vector / norm
        
        logger.info(
            "Calculated user vector",
            user_id=str(user_id),
            num_interactions=len(interactions),
            vector_norm=float(np.linalg.norm(user_vector)),
        )
        
        return user_vector.tolist()
    
    async def calculate_session_vector(
        self,
        db: AsyncSession,
        user_id: UUID,
        last_n: int = 5,
    ) -> Optional[List[float]]:
        """
        Calculate session-based preference vector from recent interactions.
        
        Args:
            db: Database session.
            user_id: User ID.
            last_n: Number of recent interactions to use.
            
        Returns:
            Session preference vector or None.
        """
        # Fetch last N interactions
        query = (
            select(Article.embedding)
            .join(UserInteraction, UserInteraction.article_id == Article.id)
            .where(
                UserInteraction.user_id == user_id,
                UserInteraction.interaction_type.in_(["view", "upvote", "bookmark", "deep_research"]),
                Article.embedding.isnot(None),
            )
            .order_by(UserInteraction.created_at.desc())
            .limit(last_n)
        )
        
        result = await db.execute(query)
        embeddings = [row[0] for row in result.all() if row[0] is not None]
        
        if not embeddings:
            return None
        
        # Simple average for session (no time decay, recent interactions only)
        emb_arrays = []
        for emb in embeddings:
            if isinstance(emb, list):
                emb_arrays.append(np.array(emb))
            else:
                emb_arrays.append(np.array(emb.tolist()))
        
        session_vector = np.mean(emb_arrays, axis=0)
        
        # L2 normalize
        norm = np.linalg.norm(session_vector)
        if norm > 0:
            session_vector = session_vector / norm
        
        return session_vector.tolist()
    
    async def get_combined_user_vector(
        self,
        db: AsyncSession,
        user: User,
    ) -> Optional[List[float]]:
        """
        Get combined user vector (long-term + session).
        
        Args:
            db: Database session.
            user: User object.
            
        Returns:
            Combined preference vector.
        """
        # Get long-term vector (from user or calculate)
        long_term = None
        if user.long_term_embedding is not None:
            if isinstance(user.long_term_embedding, list):
                long_term = np.array(user.long_term_embedding)
            else:
                long_term = np.array(user.long_term_embedding.tolist())
        
        if long_term is None:
            # Calculate fresh
            long_term_list = await self.calculate_user_vector(db, user.id)
            if long_term_list:
                long_term = np.array(long_term_list)
        
        # Get session vector
        session_list = await self.calculate_session_vector(db, user.id)
        session = np.array(session_list) if session_list else None
        
        # Combine vectors
        if long_term is None and session is None:
            return None
        
        if long_term is None:
            return session.tolist()
        
        if session is None:
            return long_term.tolist()
        
        # Weighted combination
        combined = (self.long_term_weight * long_term) + (self.session_weight * session)
        
        # L2 normalize
        norm = np.linalg.norm(combined)
        if norm > 0:
            combined = combined / norm
        
        return combined.tolist()
    
    async def update_user_long_term_vector(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> bool:
        """
        Update user's long-term embedding in database.
        
        Args:
            db: Database session.
            user_id: User ID.
            
        Returns:
            True if updated successfully.
        """
        user_vector = await self.calculate_user_vector(db, user_id)
        
        if user_vector is None:
            logger.debug("No vector to update", user_id=str(user_id))
            return False
        
        # Update user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.long_term_embedding = user_vector
            await db.commit()
            
            logger.info("Updated user long-term vector", user_id=str(user_id))
            return True
        
        return False


# Singleton instance
user_modeler = UserModeler()
