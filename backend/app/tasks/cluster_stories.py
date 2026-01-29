"""
Story Clustering Tasks

Celery tasks for detecting and clustering related stories.
Uses DBSCAN clustering on article embeddings.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

import numpy as np
from celery import shared_task
from sklearn.cluster import DBSCAN
from sqlalchemy import select, func

from app.config.logging import get_logger
from app.db import get_db_context
from app.models import Article, ArticleCluster, StoryCluster

logger = get_logger(__name__)


def run_async(coro):
    """Run async function in sync context for Celery."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(bind=True)
def cluster_recent_articles(self) -> dict:
    """
    Cluster recent articles into story groups.
    
    Runs every 6 hours via Celery Beat.
    Uses DBSCAN for density-based clustering.
    """
    return run_async(_cluster_articles_async())


async def _cluster_articles_async() -> dict:
    """Async implementation of article clustering."""
    async with get_db_context() as db:
        # Get articles from last 7 days with embeddings
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        
        result = await db.execute(
            select(Article)
            .where(
                Article.embedding.isnot(None),
                Article.published_at >= cutoff,
            )
            .order_by(Article.published_at.desc())
        )
        articles = list(result.scalars().all())
        
        if len(articles) < 5:
            logger.info("Not enough articles for clustering", count=len(articles))
            return {"message": "Not enough articles", "count": len(articles)}
        
        logger.info("Starting article clustering", article_count=len(articles))
        
        # Extract embeddings
        embeddings = []
        valid_articles = []
        
        for article in articles:
            if article.embedding is not None:
                emb = article.embedding if isinstance(article.embedding, list) else article.embedding.tolist()
                embeddings.append(emb)
                valid_articles.append(article)
        
        if len(embeddings) < 5:
            return {"message": "Not enough valid embeddings"}
        
        # Run DBSCAN clustering
        # eps: Maximum distance between samples (cosine distance)
        # min_samples: Minimum articles to form a cluster
        embeddings_array = np.array(embeddings)
        
        # Normalize embeddings for cosine distance
        norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
        normalized = embeddings_array / (norms + 1e-10)
        
        # Use cosine distance (1 - cosine_similarity)
        # DBSCAN with precomputed distances
        from sklearn.metrics.pairwise import cosine_distances
        distance_matrix = cosine_distances(normalized)
        
        clustering = DBSCAN(
            eps=0.3,  # Articles within 0.3 cosine distance
            min_samples=5,  # At least 5 articles to form a story
            metric="precomputed",
        )
        
        labels = clustering.fit_predict(distance_matrix)
        
        # Process clusters
        unique_labels = set(labels)
        unique_labels.discard(-1)  # Remove noise label
        
        clusters_created = 0
        clusters_updated = 0
        
        for label in unique_labels:
            cluster_indices = np.where(labels == label)[0]
            cluster_articles = [valid_articles[i] for i in cluster_indices]
            
            if len(cluster_articles) < 5:
                continue
            
            # Calculate cluster centroid
            cluster_embeddings = [embeddings[i] for i in cluster_indices]
            centroid = np.mean(cluster_embeddings, axis=0)
            centroid = centroid / (np.linalg.norm(centroid) + 1e-10)
            
            # Check if this matches an existing cluster
            existing_cluster = await _find_matching_cluster(
                db, centroid.tolist(), threshold=0.85
            )
            
            if existing_cluster:
                # Update existing cluster
                await _update_cluster(
                    db, existing_cluster, cluster_articles, centroid.tolist()
                )
                clusters_updated += 1
            else:
                # Create new cluster
                await _create_cluster(db, cluster_articles, centroid.tolist())
                clusters_created += 1
        
        await db.commit()
        
        logger.info(
            "Clustering complete",
            clusters_created=clusters_created,
            clusters_updated=clusters_updated,
            articles_processed=len(valid_articles),
        )
        
        return {
            "clusters_created": clusters_created,
            "clusters_updated": clusters_updated,
            "articles_processed": len(valid_articles),
        }


async def _find_matching_cluster(
    db,
    centroid: List[float],
    threshold: float = 0.85,
) -> Optional[StoryCluster]:
    """Find existing cluster matching centroid."""
    result = await db.execute(
        select(StoryCluster)
        .where(
            StoryCluster.is_active == True,
            StoryCluster.centroid_embedding.isnot(None),
        )
        .order_by(StoryCluster.centroid_embedding.cosine_distance(centroid))
        .limit(1)
    )
    cluster = result.scalar_one_or_none()
    
    if cluster and cluster.centroid_embedding:
        # Verify similarity is above threshold
        cluster_emb = np.array(
            cluster.centroid_embedding if isinstance(cluster.centroid_embedding, list)
            else cluster.centroid_embedding.tolist()
        )
        centroid_np = np.array(centroid)
        
        similarity = float(np.dot(cluster_emb, centroid_np))
        
        if similarity >= threshold:
            return cluster
    
    return None


async def _create_cluster(
    db,
    articles: List[Article],
    centroid: List[float],
) -> StoryCluster:
    """Create a new story cluster."""
    now = datetime.now(timezone.utc)
    
    # Generate title from most recent article
    articles_sorted = sorted(articles, key=lambda a: a.published_at, reverse=True)
    title = articles_sorted[0].title[:100]
    
    # Determine date range
    first_seen = min(a.published_at for a in articles)
    
    cluster = StoryCluster(
        title=title,
        description=f"Story with {len(articles)} related articles",
        first_seen=first_seen,
        last_updated=now,
        article_count=len(articles),
        is_active=True,
        status="developing",
        centroid_embedding=centroid,
    )
    
    db.add(cluster)
    await db.flush()
    
    # Link articles to cluster
    for article in articles:
        link = ArticleCluster(
            article_id=article.id,
            cluster_id=cluster.id,
            relevance_score=1.0,
        )
        db.add(link)
    
    logger.info(
        "Created story cluster",
        cluster_id=str(cluster.id),
        title=title[:50],
        article_count=len(articles),
    )
    
    return cluster


async def _update_cluster(
    db,
    cluster: StoryCluster,
    new_articles: List[Article],
    new_centroid: List[float],
) -> None:
    """Update existing cluster with new articles."""
    now = datetime.now(timezone.utc)
    
    # Get existing article IDs
    result = await db.execute(
        select(ArticleCluster.article_id).where(ArticleCluster.cluster_id == cluster.id)
    )
    existing_ids = {row[0] for row in result.all()}
    
    # Add new articles
    added = 0
    for article in new_articles:
        if article.id not in existing_ids:
            link = ArticleCluster(
                article_id=article.id,
                cluster_id=cluster.id,
                relevance_score=1.0,
            )
            db.add(link)
            added += 1
    
    # Update cluster metadata
    cluster.last_updated = now
    cluster.article_count += added
    cluster.centroid_embedding = new_centroid
    
    # Update status based on recency
    hours_since_first = (now - cluster.first_seen).total_seconds() / 3600
    
    if hours_since_first < 24:
        cluster.status = "developing"
    elif hours_since_first < 72:
        cluster.status = "ongoing"
    else:
        cluster.status = "ongoing"
    
    if added > 0:
        logger.info(
            "Updated story cluster",
            cluster_id=str(cluster.id),
            articles_added=added,
            total_articles=cluster.article_count,
        )
