/**
 * Onboarding Page
 * 
 * Two-step onboarding: topic selection, then article selection.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, Loader2, ArrowRight, Sparkles } from 'lucide-react'
import { api } from '../api/client'
import { useAuthStore } from '../hooks/useAuth'
import toast from 'react-hot-toast'

const TOPICS = [
  { id: 'technology', name: 'Technology', emoji: '💻' },
  { id: 'science', name: 'Science', emoji: '🔬' },
  { id: 'business', name: 'Business', emoji: '📈' },
  { id: 'politics', name: 'Politics', emoji: '🏛️' },
  { id: 'health', name: 'Health', emoji: '🏥' },
  { id: 'environment', name: 'Environment', emoji: '🌍' },
  { id: 'sports', name: 'Sports', emoji: '⚽' },
  { id: 'entertainment', name: 'Entertainment', emoji: '🎬' },
  { id: 'world', name: 'World News', emoji: '🌐' },
  { id: 'finance', name: 'Finance', emoji: '💰' },
]

export default function Onboarding() {
  const [step, setStep] = useState(1)
  const [selectedTopics, setSelectedTopics] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const { setUser } = useAuthStore()
  const navigate = useNavigate()
  
  const toggleTopic = (topicId: string) => {
    setSelectedTopics((prev) =>
      prev.includes(topicId)
        ? prev.filter((t) => t !== topicId)
        : prev.length < 5
        ? [...prev, topicId]
        : prev
    )
  }
  
  const handleTopicsSubmit = async () => {
    if (selectedTopics.length < 3) {
      toast.error('Please select at least 3 topics')
      return
    }
    
    setIsLoading(true)
    try {
      await api.selectTopics(selectedTopics)
      setStep(2)
    } catch (err) {
      toast.error('Failed to save topics')
    } finally {
      setIsLoading(false)
    }
  }
  
  const handleComplete = async () => {
    setIsLoading(true)
    try {
      // Skip article selection - just complete onboarding
      const result = await api.updatePreferences({
        topics: selectedTopics,
      })
      setUser(result)
      toast.success('Welcome to NewsIQ!')
      navigate('/')
    } catch (err) {
      toast.error('Failed to complete onboarding')
    } finally {
      setIsLoading(false)
    }
  }
  
  return (
    <div className="min-h-screen bg-surface-950 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-500 to-accent-500 mb-4">
            <Sparkles className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-display font-bold text-white">
            {step === 1 ? "What interests you?" : "Almost there!"}
          </h1>
          <p className="text-surface-400 mt-2">
            {step === 1
              ? "Select 3-5 topics to personalize your feed"
              : "We'll tailor your experience based on your selections"}
          </p>
        </div>
        
        {/* Progress */}
        <div className="flex items-center justify-center gap-2 mb-8">
          <div className={`w-3 h-3 rounded-full ${step >= 1 ? 'bg-primary-500' : 'bg-surface-700'}`} />
          <div className={`w-12 h-0.5 ${step >= 2 ? 'bg-primary-500' : 'bg-surface-700'}`} />
          <div className={`w-3 h-3 rounded-full ${step >= 2 ? 'bg-primary-500' : 'bg-surface-700'}`} />
        </div>
        
        {step === 1 && (
          <div className="glass-card p-6">
            {/* Topic grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
              {TOPICS.map((topic) => {
                const isSelected = selectedTopics.includes(topic.id)
                return (
                  <button
                    key={topic.id}
                    onClick={() => toggleTopic(topic.id)}
                    disabled={!isSelected && selectedTopics.length >= 5}
                    className={`relative p-4 rounded-xl border-2 transition-all duration-200 text-left
                      ${
                        isSelected
                          ? 'border-primary-500 bg-primary-500/10'
                          : 'border-surface-700 bg-surface-800/50 hover:border-surface-600'
                      }
                      ${!isSelected && selectedTopics.length >= 5 ? 'opacity-50 cursor-not-allowed' : ''}
                    `}
                  >
                    {isSelected && (
                      <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-primary-500 flex items-center justify-center">
                        <Check className="w-3 h-3 text-white" />
                      </div>
                    )}
                    <span className="text-2xl mb-2 block">{topic.emoji}</span>
                    <span className="font-medium text-white">{topic.name}</span>
                  </button>
                )
              })}
            </div>
            
            {/* Counter */}
            <p className="text-center text-surface-400 text-sm mb-6">
              {selectedTopics.length}/5 topics selected
              {selectedTopics.length < 3 && ' (minimum 3)'}
            </p>
            
            {/* Submit button */}
            <button
              onClick={handleTopicsSubmit}
              disabled={selectedTopics.length < 3 || isLoading}
              className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>
                  Continue
                  <ArrowRight className="w-5 h-5" />
                </>
              )}
            </button>
          </div>
        )}
        
        {step === 2 && (
          <div className="glass-card p-6 text-center">
            <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-primary-500/20 to-accent-500/20 flex items-center justify-center">
              <Check className="w-10 h-10 text-primary-400" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">All set!</h3>
            <p className="text-surface-400 mb-6">
              Your personalized feed is ready. We'll learn from your interactions
              to make it even better over time.
            </p>
            <button
              onClick={handleComplete}
              disabled={isLoading}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>
                  Start Reading
                  <ArrowRight className="w-5 h-5" />
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
