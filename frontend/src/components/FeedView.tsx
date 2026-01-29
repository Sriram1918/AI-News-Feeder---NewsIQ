/**
 * FeedView Component
 * 
 * Infinite scroll feed of articles.
 */

import { useEffect, useRef, useCallback } from 'react'
import { Loader2, AlertCircle, RefreshCw } from 'lucide-react'
import { useFeed } from '../hooks/useFeed'
import ArticleCard from './ArticleCard'

export default function FeedView() {
  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    isError,
    refetch,
  } = useFeed()
  
  const observerRef = useRef<IntersectionObserver | null>(null)
  const loadMoreRef = useRef<HTMLDivElement>(null)
  
  // Infinite scroll observer
  const handleObserver = useCallback((entries: IntersectionObserverEntry[]) => {
    const [target] = entries
    if (target.isIntersecting && hasNextPage && !isFetchingNextPage) {
      fetchNextPage()
    }
  }, [fetchNextPage, hasNextPage, isFetchingNextPage])
  
  useEffect(() => {
    const element = loadMoreRef.current
    if (!element) return
    
    observerRef.current = new IntersectionObserver(handleObserver, {
      threshold: 0.1,
      rootMargin: '100px',
    })
    
    observerRef.current.observe(element)
    
    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect()
      }
    }
  }, [handleObserver])
  
  // Flatten articles from all pages
  const articles = data?.pages.flatMap((page) => page.articles) ?? []
  
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Loader2 className="w-10 h-10 text-primary-400 animate-spin mb-4" />
        <p className="text-surface-400">Loading your personalized feed...</p>
      </div>
    )
  }
  
  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <AlertCircle className="w-10 h-10 text-red-400 mb-4" />
        <p className="text-surface-400 mb-4">Failed to load feed</p>
        <button onClick={() => refetch()} className="btn-primary">
          <RefreshCw className="w-4 h-4 mr-2" />
          Try Again
        </button>
      </div>
    )
  }
  
  if (articles.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="w-16 h-16 rounded-full bg-surface-800 flex items-center justify-center mb-4">
          <AlertCircle className="w-8 h-8 text-surface-500" />
        </div>
        <h3 className="text-lg font-semibold text-white mb-2">No articles yet</h3>
        <p className="text-surface-400 text-center max-w-md">
          Check back later for fresh news, or complete your onboarding to get personalized recommendations.
        </p>
      </div>
    )
  }
  
  return (
    <div className="space-y-4">
      {/* Feed header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-display font-bold text-white">Your Feed</h1>
          <p className="text-surface-400 text-sm mt-1">
            {data?.pages[0].total_count ?? 0} articles • Personalized for you
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="btn-ghost flex items-center gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>
      
      {/* Articles grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-1">
        {articles.map((article) => (
          <ArticleCard key={article.id} article={article} />
        ))}
      </div>
      
      {/* Load more trigger */}
      <div ref={loadMoreRef} className="py-8 flex justify-center">
        {isFetchingNextPage ? (
          <Loader2 className="w-6 h-6 text-primary-400 animate-spin" />
        ) : hasNextPage ? (
          <button
            onClick={() => fetchNextPage()}
            className="btn-secondary text-sm"
          >
            Load more articles
          </button>
        ) : articles.length > 0 ? (
          <p className="text-surface-500 text-sm">You've reached the end</p>
        ) : null}
      </div>
    </div>
  )
}
