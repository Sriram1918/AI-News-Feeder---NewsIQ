/**
 * API Client for News Intelligence System
 * 
 * Axios-based HTTP client with authentication interceptors
 */

import axios, { AxiosError, AxiosInstance } from 'axios'
import toast from 'react-hot-toast'

// Types
export interface Article {
  id: string
  title: string
  url: string
  summary: string | null
  author: string | null
  source: string
  source_credibility_score: number | null
  published_at: string
  topic_tags: string[] | null
  sentiment_score: number | null
  relevance_score?: number | null
  is_blind_spot: boolean
  read_time_minutes: number | null
  thumbnail_url?: string | null
}

export interface ArticleDetail extends Article {
  content: string
  entity_mentions: Record<string, string[]> | null
  fetched_at: string
  created_at: string
}

export interface FeedResponse {
  articles: Article[]
  has_more: boolean
  total_count: number
  page: number
  per_page: number
}

export interface User {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  is_verified: boolean
  onboarding_completed: boolean
  preference_topics: string[]
  muted_sources: string[]
  diversity_level: 'low' | 'medium' | 'high'
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface ResearchResponse {
  analysis: string
  related_articles: {
    id: string
    title: string
    url: string
    source: string
    published_at: string
  }[]
  generated_at: string
  from_cache: boolean
}

export interface StoryCluster {
  id: string
  title: string
  description: string | null
  status: 'developing' | 'ongoing' | 'resolved'
  article_count: number
  is_active: boolean
  first_seen: string
  last_updated: string
}

export interface TimelineEvent {
  date: string
  event: string
  article_count: number
  key_articles: Article[]
}

export interface TimelineResponse {
  cluster_id: string
  title: string
  description: string | null
  status: 'developing' | 'ongoing' | 'resolved'
  timeline: TimelineEvent[]
  current_status: string
  total_articles: number
  first_seen: string
  last_updated: string
}

// API client instance
const API_BASE_URL = '/api/v1'

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor for auth token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail: string }>) => {
    const message = error.response?.data?.detail || 'An error occurred'
    
    if (error.response?.status === 401) {
      // Token expired or invalid
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    } else if (error.response?.status === 429) {
      toast.error('Too many requests. Please wait a moment.')
    } else if (error.response?.status >= 500) {
      toast.error('Server error. Please try again later.')
    }
    
    return Promise.reject(error)
  }
)

// API functions
export const api = {
  // Auth
  register: async (data: { email: string; password: string; full_name?: string }): Promise<User> => {
    const response = await apiClient.post<User>('/user/register', data)
    return response.data
  },
  
  login: async (data: { email: string; password: string }): Promise<TokenResponse> => {
    const response = await apiClient.post<TokenResponse>('/user/login', data)
    return response.data
  },
  
  getMe: async (): Promise<User> => {
    const response = await apiClient.get<User>('/user/me')
    return response.data
  },
  
  // Feed
  getFeed: async (params: { page?: number; per_page?: number; include_blind_spots?: boolean }): Promise<FeedResponse> => {
    const response = await apiClient.get<FeedResponse>('/feed', { params })
    return response.data
  },
  
  getArticle: async (id: string): Promise<ArticleDetail> => {
    const response = await apiClient.get<ArticleDetail>(`/feed/${id}`)
    return response.data
  },
  
  // Interactions
  recordInteraction: async (data: {
    article_id: string
    interaction_type: 'view' | 'upvote' | 'downvote' | 'mute' | 'bookmark' | 'deep_research'
    read_time_seconds?: number
    scroll_depth?: number
  }): Promise<{ success: boolean; feed_updated: boolean }> => {
    const response = await apiClient.post('/user/interactions', data)
    return response.data
  },
  
  // Research
  analyzeArticle: async (articleId: string): Promise<ResearchResponse> => {
    const response = await apiClient.post<ResearchResponse>('/research/analyze', {
      article_id: articleId,
    })
    return response.data
  },
  
  // Stories
  getStories: async (params?: { active_only?: boolean; limit?: number }): Promise<StoryCluster[]> => {
    const response = await apiClient.get<StoryCluster[]>('/stories', { params })
    return response.data
  },
  
  getStoryTimeline: async (clusterId: string): Promise<TimelineResponse> => {
    const response = await apiClient.get<TimelineResponse>(`/stories/${clusterId}`)
    return response.data
  },
  
  // User preferences
  updatePreferences: async (data: {
    topics?: string[]
    muted_sources?: string[]
    diversity_level?: 'low' | 'medium' | 'high'
  }): Promise<User> => {
    const response = await apiClient.post<User>('/user/preferences', data)
    return response.data
  },
  
  // Onboarding
  selectTopics: async (topics: string[]): Promise<{ success: boolean }> => {
    const response = await apiClient.post('/user/onboarding/topics', { topics })
    return response.data
  },
  
  selectArticles: async (articleIds: string[]): Promise<{ success: boolean; user: User }> => {
    const response = await apiClient.post('/user/onboarding/articles', { article_ids: articleIds })
    return response.data
  },
}

export default apiClient
