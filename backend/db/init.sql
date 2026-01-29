-- =============================================================================
-- PostgreSQL Initialization Script for News Intelligence System
-- Requires: pgvector extension
-- =============================================================================

-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Articles Table
-- Stores all ingested news articles with embeddings
-- =============================================================================
CREATE TABLE IF NOT EXISTS articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    author TEXT,
    source TEXT NOT NULL,
    source_credibility_score INTEGER CHECK (source_credibility_score BETWEEN 0 AND 100),
    published_at TIMESTAMP NOT NULL,
    fetched_at TIMESTAMP DEFAULT NOW(),
    embedding vector(768),
    topic_tags TEXT[],
    entity_mentions JSONB DEFAULT '{"people": [], "organizations": [], "locations": []}'::jsonb,
    sentiment_score FLOAT CHECK (sentiment_score BETWEEN -1 AND 1),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- HNSW index for fast approximate nearest neighbor search
-- Using cosine distance for semantic similarity
CREATE INDEX IF NOT EXISTS idx_articles_embedding 
    ON articles USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_articles_published ON articles (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles (source);
CREATE INDEX IF NOT EXISTS idx_articles_fetched ON articles (fetched_at DESC);

-- =============================================================================
-- Users Table
-- Stores user profiles with personalization vectors
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    full_name TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    long_term_embedding vector(768),
    preference_topics TEXT[] DEFAULT '{}',
    muted_sources TEXT[] DEFAULT '{}',
    diversity_level TEXT DEFAULT 'medium' CHECK (diversity_level IN ('low', 'medium', 'high')),
    onboarding_completed BOOLEAN DEFAULT FALSE,
    last_active TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_last_active ON users (last_active DESC);

-- =============================================================================
-- User Interactions Table
-- Tracks all user-article interactions for personalization
-- =============================================================================
CREATE TABLE IF NOT EXISTS user_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    interaction_type TEXT NOT NULL CHECK (
        interaction_type IN ('view', 'upvote', 'downvote', 'mute', 'bookmark', 'deep_research')
    ),
    read_time_seconds INTEGER,
    scroll_depth_percent INTEGER CHECK (scroll_depth_percent BETWEEN 0 AND 100),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_interactions_user ON user_interactions (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_article ON user_interactions (article_id);
CREATE INDEX IF NOT EXISTS idx_interactions_type ON user_interactions (interaction_type);

-- =============================================================================
-- Story Clusters Table
-- Groups related articles into evolving story narratives
-- =============================================================================
CREATE TABLE IF NOT EXISTS story_clusters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT,
    first_seen TIMESTAMP NOT NULL,
    last_updated TIMESTAMP NOT NULL,
    article_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    centroid_embedding vector(768),
    status TEXT DEFAULT 'developing' CHECK (status IN ('developing', 'ongoing', 'resolved')),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clusters_active ON story_clusters (is_active, last_updated DESC);
CREATE INDEX IF NOT EXISTS idx_clusters_centroid 
    ON story_clusters USING hnsw (centroid_embedding vector_cosine_ops);

-- =============================================================================
-- Article-Cluster Relationships Table
-- Many-to-many relationship between articles and story clusters
-- =============================================================================
CREATE TABLE IF NOT EXISTS article_clusters (
    article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    cluster_id UUID NOT NULL REFERENCES story_clusters(id) ON DELETE CASCADE,
    relevance_score FLOAT DEFAULT 1.0,
    added_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (article_id, cluster_id)
);

CREATE INDEX IF NOT EXISTS idx_article_clusters_cluster ON article_clusters (cluster_id);

-- =============================================================================
-- Deep Research Cache Table
-- Caches generated research analysis for performance
-- =============================================================================
CREATE TABLE IF NOT EXISTS research_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    analysis_text TEXT NOT NULL,
    related_article_ids UUID[],
    generated_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    view_count INTEGER DEFAULT 0,
    invalidated BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_research_cache_article ON research_cache (article_id);
CREATE INDEX IF NOT EXISTS idx_research_cache_expires ON research_cache (expires_at);
CREATE INDEX IF NOT EXISTS idx_research_cache_valid 
    ON research_cache (article_id) WHERE invalidated = FALSE;

-- =============================================================================
-- RSS Sources Table
-- Manages RSS feed subscriptions and polling schedules
-- =============================================================================
CREATE TABLE IF NOT EXISTS rss_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    credibility_score INTEGER DEFAULT 70 CHECK (credibility_score BETWEEN 0 AND 100),
    is_active BOOLEAN DEFAULT TRUE,
    last_fetched TIMESTAMP,
    last_successful_fetch TIMESTAMP,
    fetch_interval_minutes INTEGER DEFAULT 5,
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rss_sources_active ON rss_sources (is_active, last_fetched);

-- =============================================================================
-- Session Vectors Table
-- Stores temporary session-based user preferences
-- =============================================================================
CREATE TABLE IF NOT EXISTS session_vectors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_embedding vector(768),
    interaction_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_session_vectors_user ON session_vectors (user_id);

-- =============================================================================
-- Trigger Functions
-- =============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to tables
CREATE TRIGGER update_articles_updated_at
    BEFORE UPDATE ON articles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_rss_sources_updated_at
    BEFORE UPDATE ON rss_sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Insert Initial RSS Sources (Top 10 Curated Feeds)
-- =============================================================================
INSERT INTO rss_sources (url, name, category, credibility_score) VALUES
    ('https://feeds.arstechnica.com/arstechnica/index', 'Ars Technica', 'technology', 85),
    ('https://www.theverge.com/rss/index.xml', 'The Verge', 'technology', 80),
    ('https://techcrunch.com/feed/', 'TechCrunch', 'technology', 80),
    ('https://news.ycombinator.com/rss', 'Hacker News', 'technology', 75),
    ('http://feeds.bbci.co.uk/news/rss.xml', 'BBC News', 'general', 90),
    ('https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml', 'New York Times', 'general', 90),
    ('https://feeds.npr.org/1001/rss.xml', 'NPR', 'general', 88),
    ('https://www.nature.com/nature.rss', 'Nature', 'science', 95),
    ('https://www.wired.com/feed/rss', 'Wired', 'technology', 82),
    ('https://www.economist.com/rss', 'The Economist', 'business', 92)
ON CONFLICT (url) DO NOTHING;

-- =============================================================================
-- Useful Views
-- =============================================================================

-- Recent articles with source info
CREATE OR REPLACE VIEW recent_articles_view AS
SELECT 
    a.id,
    a.title,
    a.summary,
    a.source,
    a.source_credibility_score,
    a.published_at,
    a.topic_tags,
    a.sentiment_score
FROM articles a
WHERE a.published_at > NOW() - INTERVAL '7 days'
ORDER BY a.published_at DESC;

-- Active story clusters with article counts
CREATE OR REPLACE VIEW active_clusters_view AS
SELECT 
    sc.id,
    sc.title,
    sc.description,
    sc.status,
    sc.article_count,
    sc.first_seen,
    sc.last_updated
FROM story_clusters sc
WHERE sc.is_active = TRUE
ORDER BY sc.last_updated DESC;
