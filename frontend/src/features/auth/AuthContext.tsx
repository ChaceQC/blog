import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from 'react'

import { getCurrentAdminUser, loginAdmin, logoutAdmin } from './api.ts'
import {
  clearAuthSession,
  createAuthSession,
  readAuthSession,
  saveAuthSession,
  type AuthSession,
} from './session.ts'
import { AuthContext } from './authContext.ts'

export function AuthProvider({ children }: PropsWithChildren) {
  const [initialSession] = useState<AuthSession | null>(() => readAuthSession())
  const [session, setSession] = useState<AuthSession | null>(initialSession)
  const [isChecking, setIsChecking] = useState(initialSession !== null)

  useEffect(() => {
    if (initialSession === null) {
      return
    }

    let isMounted = true

    getCurrentAdminUser(initialSession.accessToken)
      .then((user) => {
        if (!isMounted) {
          return
        }

        const nextSession = { ...initialSession, user }
        saveAuthSession(nextSession)
        setSession(nextSession)
      })
      .catch(() => {
        if (!isMounted) {
          return
        }

        clearAuthSession()
        setSession(null)
      })
      .finally(() => {
        if (isMounted) {
          setIsChecking(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [initialSession])

  const login = useCallback(async (username: string, password: string) => {
    const tokens = await loginAdmin({ username, password })
    const nextSession = createAuthSession(tokens)
    saveAuthSession(nextSession)
    setSession(nextSession)
    setIsChecking(false)
  }, [])

  const logout = useCallback(async () => {
    const currentSession = session
    clearAuthSession()
    setSession(null)
    setIsChecking(false)
    if (currentSession !== null) {
      try {
        await logoutAdmin(currentSession.refreshToken)
      } catch {
        // 本地退出优先完成；后端吊销失败由后续登录轮换策略兜底。
      }
    }
  }, [session])

  const value = useMemo(
    () => ({
      session,
      isChecking,
      login,
      logout,
    }),
    [isChecking, login, logout, session],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
