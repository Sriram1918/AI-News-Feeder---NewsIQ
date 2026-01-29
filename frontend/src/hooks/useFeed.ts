/**
 * Feed Hook using TanStack Query
 */

import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { api, FeedResponse } from '../api/client'

export function useFeed() {
  return useInfiniteQuery<FeedResponse>({
    queryKey: ['feed'],
    queryFn: ({ pageParam = 1 }) => api.getFeed({ page: pageParam as number, per_page: 20 }),
    getNextPageParam: (lastPage) => {
      if (lastPage.has_more) {
        return lastPage.page + 1
      }
      return undefined
    },
    initialPageParam: 1,
  })
}

export function useInteraction() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: api.recordInteraction,
    onSuccess: (data, variables) => {
      if (data.feed_updated) {
        // Optionally invalidate feed on certain interactions
        if (['upvote', 'downvote', 'mute'].includes(variables.interaction_type)) {
          queryClient.invalidateQueries({ queryKey: ['feed'] })
        }
      }
      
      // Show feedback for explicit actions
      if (variables.interaction_type === 'upvote') {
        toast.success('Article upvoted')
      } else if (variables.interaction_type === 'bookmark') {
        toast.success('Article bookmarked')
      } else if (variables.interaction_type === 'mute') {
        toast.success('Similar articles will be hidden')
      }
    },
    onError: () => {
      toast.error('Failed to record interaction')
    },
  })
}
