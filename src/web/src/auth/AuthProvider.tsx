import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { User } from 'oidc-client-ts'
import { getUserManager, getUser, login, logout, getAccessToken } from './oidc'

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  accessToken: string | null
  login: () => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const um = getUserManager()

    // Load user on mount
    getUser().then((u) => {
      setUser(u)
      setIsLoading(false)
    })

    // Listen for user changes
    um.events.addUserLoaded((u) => setUser(u))
    um.events.addUserUnloaded(() => setUser(null))
    um.events.addSilentRenewError(() => {
      console.error('Silent renew failed')
    })

    return () => {
      um.events.removeUserLoaded((u) => setUser(u))
      um.events.removeUserUnloaded(() => setUser(null))
    }
  }, [])

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user && !user.expired,
    isLoading,
    accessToken: getAccessToken(user),
    login,
    logout,
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
