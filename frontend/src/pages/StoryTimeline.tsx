/**
 * Story Timeline Page
 */

import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { format, formatDistanceToNow } from 'date-fns'
import {
  ArrowLeft,
  Loader2,
  Calendar,
  Newspaper,
  ExternalLink,
  TrendingUp,
  CheckCircle,
  Clock,
} from 'lucide-react'
import { api } from '../api/client'

export default function StoryTimeline() {
  const { id } = useParams<{ id: string }>()
  
  const { data: timeline, isLoading, isError } = useQuery({
    queryKey: ['story', id],
    queryFn: () => api.getStoryTimeline(id!),
    enabled: !!id,
  })
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-primary-400 animate-spin" />
      </div>
    )
  }
  
  if (isError || !timeline) {
    return (
      <div className="text-center py-20">
        <h2 className="text-xl font-semibold text-white mb-2">Story not found</h2>
        <Link to="/stories" className="text-primary-400 hover:text-primary-300">
          Return to stories
        </Link>
      </div>
    )
  }
  
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'developing':
        return 'bg-amber-500'
      case 'ongoing':
        return 'bg-primary-500'
      case 'resolved':
        return 'bg-emerald-500'
      default:
        return 'bg-surface-500'
    }
  }
  
  return (
    <div className="max-w-4xl mx-auto">
      {/* Back link */}
      <Link
        to="/stories"
        className="inline-flex items-center gap-2 text-surface-400 hover:text-white mb-6 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        All Stories
      </Link>
      
      {/* Header */}
      <header className="mb-8">
        <div className="flex items-center gap-3 mb-3">
          <div className={`w-3 h-3 rounded-full ${getStatusColor(timeline.status)}`} />
          <span className="text-sm font-medium text-surface-400 capitalize">
            {timeline.status}
          </span>
        </div>
        
        <h1 className="text-3xl font-display font-bold text-white mb-4">
          {timeline.title}
        </h1>
        
        {timeline.description && (
          <p className="text-surface-400 text-lg mb-4">
            {timeline.description}
          </p>
        )}
        
        <div className="flex flex-wrap items-center gap-4 text-sm text-surface-500">
          <span className="flex items-center gap-1">
            <Newspaper className="w-4 h-4" />
            {timeline.total_articles} articles
          </span>
          <span className="flex items-center gap-1">
            <Calendar className="w-4 h-4" />
            Started {format(new Date(timeline.first_seen), 'MMM d, yyyy')}
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-4 h-4" />
            Updated {formatDistanceToNow(new Date(timeline.last_updated), { addSuffix: true })}
          </span>
        </div>
      </header>
      
      {/* Current status card */}
      <div className="glass-card p-5 mb-8">
        <h3 className="font-semibold text-white mb-2">Current Status</h3>
        <p className="text-surface-300">{timeline.current_status}</p>
      </div>
      
      {/* Timeline */}
      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-surface-800" />
        
        {/* Timeline events */}
        <div className="space-y-6">
          {timeline.timeline.map((event, index) => (
            <div key={event.date} className="relative pl-12">
              {/* Timeline dot */}
              <div className="absolute left-2.5 top-1 w-3 h-3 rounded-full bg-primary-500 ring-4 ring-surface-950" />
              
              {/* Event content */}
              <div className="glass-card p-5">
                <div className="flex items-center justify-between mb-3">
                  <time className="text-sm font-medium text-primary-400">
                    {format(new Date(event.date), 'MMMM d, yyyy')}
                  </time>
                  <span className="text-xs text-surface-500">
                    {event.article_count} articles
                  </span>
                </div>
                
                <h4 className="text-lg font-semibold text-white mb-4">
                  {event.event}
                </h4>
                
                {/* Key articles */}
                {event.key_articles.length > 0 && (
                  <div className="space-y-2">
                    {event.key_articles.map((article) => (
                      <Link
                        key={article.id}
                        to={`/article/${article.id}`}
                        className="flex items-start gap-3 p-3 rounded-lg bg-surface-800/50 hover:bg-surface-800 transition-colors group"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-white group-hover:text-primary-400 transition-colors line-clamp-1">
                            {article.title}
                          </p>
                          <p className="text-xs text-surface-500 mt-0.5">
                            {article.source}
                          </p>
                        </div>
                        <ExternalLink className="w-4 h-4 text-surface-500 flex-shrink-0" />
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
        
        {/* End marker */}
        {timeline.status === 'resolved' && (
          <div className="relative pl-12 mt-6">
            <div className="absolute left-2 top-1 w-4 h-4 rounded-full bg-emerald-500 flex items-center justify-center">
              <CheckCircle className="w-3 h-3 text-white" />
            </div>
            <p className="text-sm text-emerald-400 font-medium">Story Resolved</p>
          </div>
        )}
      </div>
    </div>
  )
}
