/**
 * Stories Page
 * 
 * List of active story clusters.
 */

import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { Loader2, Compass, ChevronRight, Newspaper, TrendingUp, CheckCircle } from 'lucide-react'
import { api, StoryCluster } from '../api/client'

export default function Stories() {
  const { data: stories, isLoading, isError } = useQuery({
    queryKey: ['stories'],
    queryFn: () => api.getStories({ active_only: true, limit: 50 }),
  })
  
  const getStatusIcon = (status: StoryCluster['status']) => {
    switch (status) {
      case 'developing':
        return <TrendingUp className="w-4 h-4 text-amber-400" />
      case 'ongoing':
        return <Newspaper className="w-4 h-4 text-primary-400" />
      case 'resolved':
        return <CheckCircle className="w-4 h-4 text-emerald-400" />
    }
  }
  
  const getStatusLabel = (status: StoryCluster['status']) => {
    switch (status) {
      case 'developing':
        return 'Developing'
      case 'ongoing':
        return 'Ongoing'
      case 'resolved':
        return 'Resolved'
    }
  }
  
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
        <p className="text-surface-400">Failed to load stories</p>
      </div>
    )
  }
  
  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-primary-500/20 flex items-center justify-center">
            <Compass className="w-6 h-6 text-primary-400" />
          </div>
          <h1 className="text-2xl font-display font-bold text-white">
            Evolving Stories
          </h1>
        </div>
        <p className="text-surface-400">
          Track how major stories develop over time with AI-powered timelines
        </p>
      </div>
      
      {/* Stories grid */}
      {stories && stories.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          {stories.map((story) => (
            <Link
              key={story.id}
              to={`/stories/${story.id}`}
              className="glass-card p-5 hover:border-surface-700 transition-all duration-300 group"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  {getStatusIcon(story.status)}
                  <span className="text-xs font-medium text-surface-400">
                    {getStatusLabel(story.status)}
                  </span>
                </div>
                <span className="text-xs text-surface-500">
                  {formatDistanceToNow(new Date(story.last_updated), { addSuffix: true })}
                </span>
              </div>
              
              <h3 className="text-lg font-semibold text-white mb-2 group-hover:text-primary-400 transition-colors line-clamp-2">
                {story.title}
              </h3>
              
              {story.description && (
                <p className="text-sm text-surface-400 line-clamp-2 mb-4">
                  {story.description}
                </p>
              )}
              
              <div className="flex items-center justify-between pt-3 border-t border-surface-800">
                <span className="text-sm text-surface-500">
                  {story.article_count} articles
                </span>
                <span className="flex items-center gap-1 text-primary-400 text-sm font-medium group-hover:gap-2 transition-all">
                  View Timeline
                  <ChevronRight className="w-4 h-4" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="text-center py-20">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-surface-800 flex items-center justify-center">
            <Compass className="w-8 h-8 text-surface-500" />
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">No stories yet</h3>
          <p className="text-surface-400">
            Story clusters will appear as related articles are detected
          </p>
        </div>
      )}
    </div>
  )
}
