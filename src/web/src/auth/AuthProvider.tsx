import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react'
import { User } from 'oidc-client-ts'
import { getUserManager, getUser, login, logout, getAccessToken, silentRenew } from './oidc'

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  accessToken: string | null
  login: () => Promise<void>
  logout: () => Promise<void>
  refreshToken: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Manual token refresh function
  const refreshToken = useCallback(async () => {
    try {
      const newUser = await silentRenew()
      if (newUser) {
        setUser(newUser)
        console.log('Token refreshed successfully')
      } else {
        console.warn('Token refresh returned null, redirecting to login')
        await login()
      }
    } catch (error) {
      console.error('Token refresh failed:', error)
      await login()
    }
  }, [])

  useEffect(() => {
    const um = getUserManager()

    // Load user on mount
    getUser().then((u) => {
      // If user exists but token is expired, try to refresh
      if (u && u.expired) {
        console.log('Token expired on load, attempting refresh')
        silentRenew().then((newUser) => {
          setUser(newUser)
          setIsLoading(false)
        }).catch(() => {
          setUser(null)
          setIsLoading(false)
        })
      } else {
        setUser(u)
        setIsLoading(false)
      }
    })

    // Listen for user changes
    const handleUserLoaded = (u: User) => {
      console.log('User loaded, token expires at:', new Date(u.expires_at! * 1000))
      setUser(u)
    }

    const handleUserUnloaded = () => {
      console.log('User unloaded')
      setUser(null)
    }

    const handleSilentRenewError = (error: Error) => {
      console.error('Silent renew failed:', error)
      // On silent renew failure, redirect to login after a short delay
      setTimeout(() => {
        login()
      }, 1000)
    }

    const handleAccessTokenExpiring = () => {
      console.log('Access token expiring soon, will auto-renew')
    }

    const handleAccessTokenExpired = () => {
      console.warn('Access token expired')
      // Try one more silent renew before redirecting
      silentRenew().catch(() => {
        console.error('Final refresh attempt failed, redirecting to login')
        login()
      })
    }

    um.events.addUserLoaded(handleUserLoaded)
    um.events.addUserUnloaded(handleUserUnloaded)
    um.events.addSilentRenewError(handleSilentRenewError)
    um.events.addAccessTokenExpiring(handleAccessTokenExpiring)
    um.events.addAccessTokenExpired(handleAccessTokenExpired)

    return () => {
      um.events.removeUserLoaded(handleUserLoaded)
      um.events.removeUserUnloaded(handleUserUnloaded)
      um.events.removeSilentRenewError(handleSilentRenewError)
      um.events.removeAccessTokenExpiring(handleAccessTokenExpiring)
      um.events.removeAccessTokenExpired(handleAccessTokenExpired)
    }
  }, [])

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user && !user.expired,
    isLoading,
    accessToken: getAccessToken(user),
    login,
    logout,
    refreshToken,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
