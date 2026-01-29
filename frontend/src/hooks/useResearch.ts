/**
 * Deep Research Hook
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { api, ResearchResponse } from '../api/client'

export function useResearch(articleId: string | null) {
  const queryClient = useQueryClient()
  
  const mutation = useMutation({
    mutationFn: (id: string) => api.analyzeArticle(id),
    onSuccess: (data) => {
      // Cache the result
      if (articleId) {
        queryClient.setQueryData(['research', articleId], data)
      }
    },
    onError: () => {
      toast.error('Failed to generate analysis')
    },
  })
  
  // Get cached result if available
  const cachedData = queryClient.getQueryData<ResearchResponse>(['research', articleId])
  
  return {
    analyze: mutation.mutate,
    isLoading: mutation.isPending,
    data: mutation.data || cachedData,
    error: mutation.error,
    reset: mutation.reset,
  }
}

export function useArticleDetail(articleId: string | undefined) {
  return useQuery({
    queryKey: ['article', articleId],
    queryFn: () => api.getArticle(articleId!),
    enabled: !!articleId,
  })
}
