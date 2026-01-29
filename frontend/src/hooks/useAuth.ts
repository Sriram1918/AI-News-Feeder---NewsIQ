/**
 * Authentication Store using Zustand
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api, User } from '../api/client'

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  
  // Actions
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, fullName?: string) => Promise<void>
  logout: () => void
  fetchUser: () => Promise<void>
  setUser: (user: User) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      
      login: async (email: string, password: string) => {
        set({ isLoading: true })
        try {
          const response = await api.login({ email, password })
          localStorage.setItem('access_token', response.access_token)
          
          const user = await api.getMe()
          set({ user, isAuthenticated: true, isLoading: false })
        } catch (error) {
          set({ isLoading: false })
          throw error
        }
      },
      
      register: async (email: string, password: string, fullName?: string) => {
        set({ isLoading: true })
        try {
          await api.register({ email, password, full_name: fullName })
          // Auto-login after registration
          const response = await api.login({ email, password })
          localStorage.setItem('access_token', response.access_token)
          
          const user = await api.getMe()
          set({ user, isAuthenticated: true, isLoading: false })
        } catch (error) {
          set({ isLoading: false })
          throw error
        }
      },
      
      logout: () => {
        localStorage.removeItem('access_token')
        set({ user: null, isAuthenticated: false })
      },
      
      fetchUser: async () => {
        const token = localStorage.getItem('access_token')
        if (!token) {
          set({ isAuthenticated: false })
          return
        }
        
        set({ isLoading: true })
        try {
          const user = await api.getMe()
          set({ user, isAuthenticated: true, isLoading: false })
        } catch {
          set({ user: null, isAuthenticated: false, isLoading: false })
        }
      },
      
      setUser: (user: User) => {
        set({ user })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ isAuthenticated: state.isAuthenticated }),
    }
  )
)
