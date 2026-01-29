"""
Embedding Generator Service

Generates embeddings using Google Gemini's text-embedding-004 model.
Following official Google Generative AI Python SDK documentation:
https://github.com/google-gemini/generative-ai-python
"""

import asyncio
from typing import List, Optional

import numpy as np
import google.generativeai as genai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config.logging import get_logger
from app.config.settings import settings

logger = get_logger(__name__)


class EmbeddingError(Exception):
    """Exception raised when embedding generation fails."""
    pass


class EmbeddingGenerator:
    """
    Embedding Generator using Google Gemini's API.
    
    Features:
    - Async embedding generation
    - Batch processing with rate limiting
    - Retry logic for transient failures
    - Text preprocessing
    """
    
    def __init__(self):
        """Initialize the embedding generator."""
        genai.configure(api_key=settings.google_api_key)
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions
        self.batch_size = settings.embedding_batch_size
        
        logger.info(
            "Initialized EmbeddingGenerator",
            model=self.model,
            dimensions=self.dimensions,
        )
    
    def preprocess_text(self, text: str, max_tokens: int = 8000) -> str:
        """
        Preprocess text for embedding generation.
        
        Args:
            text: Input text to preprocess.
            max_tokens: Approximate maximum tokens (uses char count heuristic).
            
        Returns:
            Preprocessed text.
        """
        if not text:
            return ""
        
        # Clean whitespace
        text = " ".join(text.split())
        
        # Truncate to approximate token limit
        # Gemini uses ~4 chars per token on average
        max_chars = max_tokens * 4
        if len(text) > max_chars:
            text = text[:max_chars]
            # Try to cut at a sentence boundary
            last_period = text.rfind(".")
            if last_period > max_chars * 0.8:
                text = text[:last_period + 1]
        
        return text
    
    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def generate(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to generate embedding for.
            
        Returns:
            List of floats representing the embedding vector.
            
        Raises:
            EmbeddingError: If embedding generation fails.
        """
        processed_text = self.preprocess_text(text)
        
        if not processed_text:
            logger.warning("Empty text provided for embedding")
            # Return zero vector for empty text
            return [0.0] * self.dimensions
        
        try:
            # Run sync API in thread pool for async compatibility
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: genai.embed_content(
                    model=self.model,
                    content=processed_text,
                    task_type="retrieval_document",
                )
            )
            
            embedding = response["embedding"]
            
            logger.debug(
                "Generated embedding",
                text_length=len(processed_text),
                embedding_dimensions=len(embedding),
            )
            
            return embedding
            
        except Exception as e:
            logger.error(
                "Failed to generate embedding",
                error=str(e),
                text_length=len(processed_text),
            )
            raise EmbeddingError(f"Failed to generate embedding: {str(e)}")
    
    async def generate_batch(
        self,
        texts: List[str],
        show_progress: bool = False,
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.
        
        Args:
            texts: List of texts to generate embeddings for.
            show_progress: Whether to log progress.
            
        Returns:
            List of embedding vectors.
            
        Raises:
            EmbeddingError: If batch embedding generation fails.
        """
        if not texts:
            return []
        
        # Preprocess all texts
        processed_texts = [self.preprocess_text(t) for t in texts]
        
        # Replace empty texts with placeholder
        for i, text in enumerate(processed_texts):
            if not text:
                processed_texts[i] = " "  # Gemini requires non-empty input
        
        embeddings = []
        total_batches = (len(processed_texts) + self.batch_size - 1) // self.batch_size
        
        for batch_idx in range(0, len(processed_texts), self.batch_size):
            batch = processed_texts[batch_idx:batch_idx + self.batch_size]
            current_batch = batch_idx // self.batch_size + 1
            
            if show_progress:
                logger.info(
                    f"Processing embedding batch {current_batch}/{total_batches}",
                    batch_size=len(batch),
                )
            
            try:
                # Run sync API in thread pool for async compatibility
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda b=batch: genai.embed_content(
                        model=self.model,
                        content=b,
                        task_type="retrieval_document",
                    )
                )
                
                # Extract embeddings - Gemini returns list of embeddings for batch
                batch_embeddings = response["embedding"]
                
                # If single item, wrap in list
                if batch and len(batch) == 1:
                    batch_embeddings = [batch_embeddings]
                
                embeddings.extend(batch_embeddings)
                
                logger.debug(
                    "Batch embedding complete",
                    batch_number=current_batch,
                    batch_size=len(batch),
                )
                
                # Small delay between batches to avoid rate limits
                if batch_idx + self.batch_size < len(processed_texts):
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                logger.error(
                    "Batch embedding failed",
                    batch_number=current_batch,
                    error=str(e),
                )
                raise EmbeddingError(f"Batch embedding failed: {str(e)}")
        
        return embeddings
    
    def cosine_similarity(
        self,
        embedding_a: List[float],
        embedding_b: List[float],
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding_a: First embedding vector.
            embedding_b: Second embedding vector.
            
        Returns:
            Cosine similarity score between -1 and 1.
        """
        a = np.array(embedding_a)
        b = np.array(embedding_b)
        
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot_product / (norm_a * norm_b))
    
    def average_embeddings(
        self,
        embeddings: List[List[float]],
        weights: Optional[List[float]] = None,
    ) -> List[float]:
        """
        Calculate weighted average of embeddings.
        
        Args:
            embeddings: List of embedding vectors.
            weights: Optional weights for each embedding.
            
        Returns:
            Averaged embedding vector.
        """
        if not embeddings:
            return [0.0] * self.dimensions
        
        np_embeddings = np.array(embeddings)
        
        if weights is None:
            avg = np.mean(np_embeddings, axis=0)
        else:
            weights = np.array(weights)
            # Normalize weights
            weights = weights / weights.sum()
            avg = np.average(np_embeddings, axis=0, weights=weights)
        
        # Normalize the result (L2 normalization)
        norm = np.linalg.norm(avg)
        if norm > 0:
            avg = avg / norm
        
        return avg.tolist()


# Singleton instance
embedding_generator = EmbeddingGenerator()
