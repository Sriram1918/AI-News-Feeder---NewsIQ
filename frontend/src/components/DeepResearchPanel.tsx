/**
 * Deep Research Panel Component
 * 
 * Modal panel showing AI-generated context analysis.
 */

import { useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { X, Loader2, ExternalLink, Clock, RefreshCw } from 'lucide-react'
import { useResearch } from '../hooks/useResearch'
import { useInteraction } from '../hooks/useFeed'
import { formatDistanceToNow } from 'date-fns'

interface DeepResearchPanelProps {
  articleId: string
  articleTitle: string
  onClose: () => void
}

export default function DeepResearchPanel({ 
  articleId, 
  articleTitle, 
  onClose 
}: DeepResearchPanelProps) {
  const { analyze, isLoading, data, reset } = useResearch(articleId)
  const interaction = useInteraction()
  
  // Trigger analysis on mount
  useEffect(() => {
    analyze(articleId)
    
    // Record deep research interaction
    interaction.mutate({
      article_id: articleId,
      interaction_type: 'deep_research',
    })
    
    // Handle escape key
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [articleId])
  
  const handleRefresh = () => {
    reset()
    analyze(articleId)
  }
  
  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full max-w-2xl max-h-[80vh] glass-card overflow-hidden animate-slide-up">
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-surface-800">
          <div className="flex-1 pr-4">
            <h2 className="text-lg font-semibold text-white mb-1">
              Deep Research
            </h2>
            <p className="text-sm text-surface-400 line-clamp-1">
              {articleTitle}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {data && !isLoading && (
              <button
                onClick={handleRefresh}
                className="btn-ghost p-2"
                aria-label="Refresh analysis"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={onClose}
              className="btn-ghost p-2"
              aria-label="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
        
        {/* Content */}
        <div className="p-5 overflow-y-auto max-h-[60vh] custom-scrollbar">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-primary-400 animate-spin mb-4" />
              <p className="text-surface-400">Analyzing article...</p>
              <p className="text-sm text-surface-500 mt-1">
                Retrieving related sources and generating context
              </p>
            </div>
          ) : data ? (
            <>
              {/* Cache indicator */}
              <div className="flex items-center justify-between mb-4 pb-4 border-b border-surface-800">
                <div className="flex items-center gap-2 text-xs text-surface-500">
                  <Clock className="w-3 h-3" />
                  {data.from_cache ? 'Cached' : 'Fresh'} analysis
                  <span className="text-surface-600">•</span>
                  {formatDistanceToNow(new Date(data.generated_at), { addSuffix: true })}
                </div>
              </div>
              
              {/* Analysis content */}
              <div className="article-content prose prose-invert max-w-none">
                <ReactMarkdown>{data.analysis}</ReactMarkdown>
              </div>
              
              {/* Related articles */}
              {data.related_articles.length > 0 && (
                <div className="mt-6 pt-6 border-t border-surface-800">
                  <h3 className="text-sm font-semibold text-surface-300 mb-3">
                    Related Sources
                  </h3>
                  <div className="space-y-2">
                    {data.related_articles.map((article) => (
                      <a
                        key={article.id}
                        href={article.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-start gap-3 p-3 rounded-lg bg-surface-800/50 
                                 hover:bg-surface-800 transition-colors group"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-white group-hover:text-primary-400 transition-colors line-clamp-1">
                            {article.title}
                          </p>
                          <p className="text-xs text-surface-500 mt-0.5">
                            {article.source} • {formatDistanceToNow(new Date(article.published_at), { addSuffix: true })}
                          </p>
                        </div>
                        <ExternalLink className="w-4 h-4 text-surface-500 flex-shrink-0 mt-0.5" />
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-surface-400">
              <p>Failed to load analysis</p>
              <button onClick={handleRefresh} className="btn-ghost mt-2">
                Try again
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
