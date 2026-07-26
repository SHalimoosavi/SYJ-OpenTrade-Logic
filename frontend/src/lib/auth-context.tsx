import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { authApi, type LoginPayload, type RegisterPayload } from '@/lib/auth-api'
import { tokenStorage } from '@/lib/api-client'
import type { User } from '@/types/api'

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (payload: LoginPayload) => Promise<void>
  register: (payload: RegisterPayload) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  async function refetchUser() {
    if (!tokenStorage.getAccess()) {
      setUser(null)
      setIsLoading(false)
      return
    }
    try {
      const me = await authApi.me()
      setUser(me)
    } catch {
      tokenStorage.clear()
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    refetchUser()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function login(payload: LoginPayload) {
    const tokens = await authApi.login(payload)
    tokenStorage.set(tokens)
    await refetchUser()
  }

  async function register(payload: RegisterPayload) {
    const tokens = await authApi.register(payload)
    tokenStorage.set(tokens)
    await refetchUser()
  }

  function logout() {
    tokenStorage.clear()
    setUser(null)
  }

  return (
    <AuthContext.Provider
      value={{ user, isLoading, isAuthenticated: !!user, login, register, logout }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
