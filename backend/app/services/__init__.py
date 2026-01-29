"""
Services Package.

Exports all services.
"""

from app.services.ingestion import (
    ContentExtractionError,
    ContentExtractor,
    EmbeddingError,
    EmbeddingGenerator,
    ExtractedContent,
    RSSFetchError,
    RSSFetcher,
    content_extractor,
    embedding_generator,
    rss_fetcher,
)
from app.services.personalization import (
    FeedRanker,
    UserModeler,
    feed_ranker,
    user_modeler,
)
from app.services.research import (
    Analyzer,
    CacheManager,
    Retriever,
    analyzer,
    cache_manager,
    retriever,
)

__all__ = [
    # Ingestion
    "RSSFetcher",
    "RSSFetchError",
    "rss_fetcher",
    "ContentExtractor",
    "ContentExtractionError",
    "ExtractedContent",
    "content_extractor",
    "EmbeddingGenerator",
    "EmbeddingError",
    "embedding_generator",
    # Personalization
    "UserModeler",
    "user_modeler",
    "FeedRanker",
    "feed_ranker",
    # Research
    "Retriever",
    "retriever",
    "Analyzer",
    "analyzer",
    "CacheManager",
    "cache_manager",
]
