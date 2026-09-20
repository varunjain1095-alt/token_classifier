import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'

interface SessionInfo {
  sessionId: string
  sessionType: 'anonymous' | 'signed_in'
  userId?: string
  projectId?: string
  freePreviewUsed: boolean
  expiresAt?: string
}

interface AuthContextType {
  session: SessionInfo | null
  isLoading: boolean
  createAnonymousSession: () => Promise<void>
  createSignedInSession: (userId: string, projectId: string) => Promise<void>
  clearSession: () => void
  isAuthenticated: boolean
  isAnonymous: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

interface AuthProviderProps {
  children: ReactNode
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [session, setSession] = useState<SessionInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Check for existing session on mount
    const existingSession = localStorage.getItem('session')
    if (existingSession) {
      try {
        const sessionData = JSON.parse(existingSession)
        setSession(sessionData)
      } catch (error) {
        console.error('Failed to parse session data:', error)
        localStorage.removeItem('session')
      }
    }
    setIsLoading(false)
  }, [])

  const createAnonymousSession = async () => {
    try {
      const response = await fetch('/api/session/anonymous', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (response.ok) {
        const data = await response.json()
        const sessionInfo: SessionInfo = {
          sessionId: data.session_id,
          sessionType: 'anonymous',
          freePreviewUsed: false,
          expiresAt: data.expires_at,
        }
        setSession(sessionInfo)
        localStorage.setItem('session', JSON.stringify(sessionInfo))
      } else {
        throw new Error('Failed to create anonymous session')
      }
    } catch (error) {
      console.error('Error creating anonymous session:', error)
      throw error
    }
  }

  const createSignedInSession = async (userId: string, projectId: string) => {
    try {
      const response = await fetch('/api/session/signed-in', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId, project_id: projectId }),
      })

      if (response.ok) {
        const data = await response.json()
        const sessionInfo: SessionInfo = {
          sessionId: data.session_id,
          sessionType: 'signed_in',
          userId,
          projectId,
          freePreviewUsed: false,
          expiresAt: data.expires_at,
        }
        setSession(sessionInfo)
        localStorage.setItem('session', JSON.stringify(sessionInfo))
      } else {
        throw new Error('Failed to create signed-in session')
      }
    } catch (error) {
      console.error('Error creating signed-in session:', error)
      throw error
    }
  }

  const clearSession = () => {
    setSession(null)
    localStorage.removeItem('session')
  }

  const isAuthenticated = session !== null && session.sessionType === 'signed_in'
  const isAnonymous = session !== null && session.sessionType === 'anonymous'

  const value: AuthContextType = {
    session,
    isLoading,
    createAnonymousSession,
    createSignedInSession,
    clearSession,
    isAuthenticated,
    isAnonymous,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
