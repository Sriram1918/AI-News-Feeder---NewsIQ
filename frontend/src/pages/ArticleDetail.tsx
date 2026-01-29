/**
 * Article Detail Page
 */

import { useParams, Link } from 'react-router-dom'
import { useState } from 'react'
import { formatDistanceToNow, format } from 'date-fns'
import {
  ArrowLeft,
  Clock,
  ExternalLink,
  ThumbsUp,
  ThumbsDown,
  Bookmark,
  Share2,
  Sparkles,
  Loader2,
} from 'lucide-react'
import { useArticleDetail } from '../hooks/useResearch'
import { useInteraction } from '../hooks/useFeed'
import DeepResearchPanel from '../components/DeepResearchPanel'

export default function ArticleDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: article, isLoading, isError } = useArticleDetail(id)
  const [showResearch, setShowResearch] = useState(false)
  const interaction = useInteraction()
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-primary-400 animate-spin" />
      </div>
    )
  }
  
  if (isError || !article) {
    return (
      <div className="text-center py-20">
        <h2 className="text-xl font-semibold text-white mb-2">Article not found</h2>
        <Link to="/" className="text-primary-400 hover:text-primary-300">
          Return to feed
        </Link>
      </div>
    )
  }
  
  const wordCount = article.content.split(/\s+/).length
  const readTime = Math.max(1, Math.ceil(wordCount / 200))
  
  return (
    <article className="max-w-3xl mx-auto">
      {/* Back button */}
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-surface-400 hover:text-white mb-6 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to feed
      </Link>
      
      {/* Header */}
      <header className="mb-8">
        <div className="flex items-center gap-3 mb-4 text-sm text-surface-400">
          <span className="font-medium text-surface-200">{article.source}</span>
          <span>•</span>
          <time>{format(new Date(article.published_at), 'MMM d, yyyy')}</time>
          <span>•</span>
          <span className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" />
            {readTime} min read
          </span>
        </div>
        
        <h1 className="text-3xl md:text-4xl font-display font-bold text-white mb-4 leading-tight">
          {article.title}
        </h1>
        
        {article.author && (
          <p className="text-surface-400">By {article.author}</p>
        )}
        
        {/* Tags */}
        {article.topic_tags && article.topic_tags.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4">
            {article.topic_tags.map((tag) => (
              <span key={tag} className="badge-primary">
                {tag}
              </span>
            ))}
          </div>
        )}
      </header>
      
      {/* Actions bar */}
      <div className="flex items-center justify-between py-4 border-y border-surface-800 mb-8">
        <div className="flex items-center gap-2">
          <button
            onClick={() => interaction.mutate({ article_id: article.id, interaction_type: 'upvote' })}
            className="btn-ghost flex items-center gap-1"
          >
            <ThumbsUp className="w-4 h-4" />
            <span className="hidden sm:inline">Like</span>
          </button>
          <button
            onClick={() => interaction.mutate({ article_id: article.id, interaction_type: 'downvote' })}
            className="btn-ghost flex items-center gap-1"
          >
            <ThumbsDown className="w-4 h-4" />
          </button>
          <button
            onClick={() => interaction.mutate({ article_id: article.id, interaction_type: 'bookmark' })}
            className="btn-ghost flex items-center gap-1"
          >
            <Bookmark className="w-4 h-4" />
            <span className="hidden sm:inline">Save</span>
          </button>
          <button
            onClick={() => navigator.share?.({ title: article.title, url: article.url })}
            className="btn-ghost flex items-center gap-1"
          >
            <Share2 className="w-4 h-4" />
            <span className="hidden sm:inline">Share</span>
          </button>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowResearch(true)}
            className="btn-primary text-sm py-2 flex items-center gap-2"
          >
            <Sparkles className="w-4 h-4" />
            Explain This
          </button>
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary text-sm py-2 flex items-center gap-2"
          >
            <ExternalLink className="w-4 h-4" />
            Original
          </a>
        </div>
      </div>
      
      {/* Content */}
      <div className="article-content text-lg leading-relaxed">
        {article.content.split('\n\n').map((paragraph, i) => (
          <p key={i} className="mb-6">
            {paragraph}
          </p>
        ))}
      </div>
      
      {/* Research panel */}
      {showResearch && (
        <DeepResearchPanel
          articleId={article.id}
          articleTitle={article.title}
          onClose={() => setShowResearch(false)}
        />
      )}
    </article>
  )
}
