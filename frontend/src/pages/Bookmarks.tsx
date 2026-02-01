/**
 * Bookmarks Page
 * 
 * Display user's saved/bookmarked articles.
 */

import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { Loader2, BookMarked, ExternalLink, Clock, Sparkles } from 'lucide-react'
import { api, Article } from '../api/client'

export default function Bookmarks() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['bookmarks'],
    queryFn: () => api.getBookmarks({ page: 1, per_page: 50 }),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-primary-400 animate-spin" />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="text-center py-20">
        <p className="text-surface-400">Failed to load bookmarks</p>
      </div>
    )
  }

  const articles = data?.articles || []

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-primary-500/20 flex items-center justify-center">
            <BookMarked className="w-6 h-6 text-primary-400" />
          </div>
          <h1 className="text-2xl font-display font-bold text-white">
            Saved Articles
          </h1>
        </div>
        <p className="text-surface-400">
          {articles.length} article{articles.length !== 1 ? 's' : ''} saved
        </p>
      </div>

      {/* Articles list */}
      {articles.length > 0 ? (
        <div className="space-y-4">
          {articles.map((article: Article) => (
            <Link
              key={article.id}
              to={`/article/${article.id}`}
              className="glass-card p-5 hover:border-surface-700 transition-all duration-300 block group"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  {/* Source and time */}
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-medium text-primary-400">
                      {article.source}
                    </span>
                    {article.source_credibility_score && (
                      <span className="text-xs text-surface-500">
                        {article.source_credibility_score}%
                      </span>
                    )}
                    <span className="text-xs text-surface-500">•</span>
                    <span className="text-xs text-surface-500">
                      {formatDistanceToNow(new Date(article.published_at), { addSuffix: true })}
                    </span>
                  </div>

                  {/* Title */}
                  <h3 className="text-lg font-semibold text-white mb-2 group-hover:text-primary-400 transition-colors line-clamp-2">
                    {article.title}
                  </h3>

                  {/* Summary */}
                  {article.summary && (
                    <p className="text-sm text-surface-400 line-clamp-2 mb-3">
                      {article.summary}
                    </p>
                  )}

                  {/* Meta info */}
                  <div className="flex items-center gap-4 text-xs text-surface-500">
                    {article.read_time_minutes && (
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        <span>{article.read_time_minutes} min read</span>
                      </div>
                    )}
                    {article.topic_tags && article.topic_tags.length > 0 && (
                      <div className="flex items-center gap-1">
                        {article.topic_tags.slice(0, 3).map((tag) => (
                          <span
                            key={tag}
                            className="px-2 py-0.5 rounded-full bg-surface-800 text-surface-300"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={(e) => {
                      e.preventDefault()
                      window.open(article.url, '_blank')
                    }}
                    className="p-2 rounded-lg hover:bg-surface-800 text-surface-400 hover:text-white transition-colors"
                    title="Open original"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="text-center py-20">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-surface-800 flex items-center justify-center">
            <BookMarked className="w-8 h-8 text-surface-500" />
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">No saved articles</h3>
          <p className="text-surface-400 mb-6">
            Bookmark articles from your feed to save them here
          </p>
          <Link
            to="/"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary-500 text-white hover:bg-primary-600 transition-colors"
          >
            <Sparkles className="w-4 h-4" />
            Browse Feed
          </Link>
        </div>
      )}
    </div>
  )
}
