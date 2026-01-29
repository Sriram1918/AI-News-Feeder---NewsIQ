/**
 * ArticleCard Component
 * 
 * Displays a single article in the feed with interactions.
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import {
  ThumbsUp,
  ThumbsDown,
  Bookmark,
  Share2,
  Clock,
  ExternalLink,
  Sparkles,
  Eye,
  TrendingUp
} from 'lucide-react'
import { Article } from '../api/client'
import { useInteraction } from '../hooks/useFeed'
import DeepResearchPanel from './DeepResearchPanel'

interface ArticleCardProps {
  article: Article
}

export default function ArticleCard({ article }: ArticleCardProps) {
  const [showResearch, setShowResearch] = useState(false)
  const [isBookmarked, setIsBookmarked] = useState(false)
  const [vote, setVote] = useState<'up' | 'down' | null>(null)
  const interaction = useInteraction()
  
  const handleVote = (type: 'up' | 'down') => {
    const newVote = vote === type ? null : type
    setVote(newVote)
    
    if (newVote) {
      interaction.mutate({
        article_id: article.id,
        interaction_type: type === 'up' ? 'upvote' : 'downvote',
      })
    }
  }
  
  const handleBookmark = () => {
    setIsBookmarked(!isBookmarked)
    if (!isBookmarked) {
      interaction.mutate({
        article_id: article.id,
        interaction_type: 'bookmark',
      })
    }
  }
  
  const handleShare = async () => {
    if (navigator.share) {
      await navigator.share({
        title: article.title,
        url: article.url,
      })
    } else {
      await navigator.clipboard.writeText(article.url)
    }
  }
  
  const credibilityColor = () => {
    const score = article.source_credibility_score ?? 70
    if (score >= 85) return 'text-emerald-400'
    if (score >= 70) return 'text-primary-400'
    if (score >= 50) return 'text-amber-400'
    return 'text-red-400'
  }
  
  return (
    <>
      <article className="glass-card p-5 hover:border-surface-700 transition-all duration-300 group animate-fade-in">
        {/* Blind Spot Badge */}
        {article.is_blind_spot && (
          <div className="mb-3">
            <span className="blind-spot-badge">
              <Eye className="w-3 h-3" />
              Blind Spot
            </span>
          </div>
        )}
        
        {/* Header: Source & Date */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="font-medium text-surface-200">{article.source}</span>
            <span className={`text-xs ${credibilityColor()}`}>
              {article.source_credibility_score ?? 70}%
            </span>
          </div>
          <time className="text-sm text-surface-500">
            {formatDistanceToNow(new Date(article.published_at), { addSuffix: true })}
          </time>
        </div>
        
        {/* Title */}
        <h2 className="text-lg font-semibold text-white mb-2 group-hover:text-primary-400 transition-colors">
          <Link to={`/article/${article.id}`} className="hover:underline">
            {article.title}
          </Link>
        </h2>
        
        {/* Summary */}
        {article.summary && (
          <p className="text-surface-400 text-sm mb-4 line-clamp-2">
            {article.summary}
          </p>
        )}
        
        {/* Meta: Read time & Tags */}
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          {article.read_time_minutes && (
            <span className="flex items-center gap-1 text-xs text-surface-500">
              <Clock className="w-3 h-3" />
              {article.read_time_minutes} min read
            </span>
          )}
          {article.topic_tags?.slice(0, 3).map((tag) => (
            <span key={tag} className="badge-primary text-xs">
              {tag}
            </span>
          ))}
          {article.sentiment_score && article.sentiment_score > 0.3 && (
            <span className="badge-accent text-xs flex items-center gap-1">
              <TrendingUp className="w-3 h-3" />
              Positive
            </span>
          )}
        </div>
        
        {/* Actions */}
        <div className="flex items-center justify-between pt-3 border-t border-surface-800">
          <div className="flex items-center gap-1">
            {/* Upvote */}
            <button
              onClick={() => handleVote('up')}
              className={`btn-ghost p-2 ${vote === 'up' ? 'text-primary-400 bg-primary-500/10' : ''}`}
              aria-label="Upvote"
            >
              <ThumbsUp className="w-4 h-4" />
            </button>
            
            {/* Downvote */}
            <button
              onClick={() => handleVote('down')}
              className={`btn-ghost p-2 ${vote === 'down' ? 'text-red-400 bg-red-500/10' : ''}`}
              aria-label="Downvote"
            >
              <ThumbsDown className="w-4 h-4" />
            </button>
            
            {/* Bookmark */}
            <button
              onClick={handleBookmark}
              className={`btn-ghost p-2 ${isBookmarked ? 'text-accent-400 bg-accent-500/10' : ''}`}
              aria-label="Bookmark"
            >
              <Bookmark className={`w-4 h-4 ${isBookmarked ? 'fill-current' : ''}`} />
            </button>
            
            {/* Share */}
            <button
              onClick={handleShare}
              className="btn-ghost p-2"
              aria-label="Share"
            >
              <Share2 className="w-4 h-4" />
            </button>
          </div>
          
          <div className="flex items-center gap-2">
            {/* Explain This */}
            <button
              onClick={() => setShowResearch(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-primary-600/20 to-accent-600/20 
                       border border-primary-500/30 rounded-lg text-sm font-medium text-primary-300
                       hover:from-primary-600/30 hover:to-accent-600/30 transition-all"
            >
              <Sparkles className="w-4 h-4" />
              Explain This
            </button>
            
            {/* External Link */}
            <a
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost p-2"
              aria-label="Open original"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>
        </div>
      </article>
      
      {/* Deep Research Panel */}
      {showResearch && (
        <DeepResearchPanel
          articleId={article.id}
          articleTitle={article.title}
          onClose={() => setShowResearch(false)}
        />
      )}
    </>
  )
}
