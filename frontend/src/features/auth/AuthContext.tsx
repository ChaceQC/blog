import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from 'react'

import { getCurrentAdminSession, loginAdmin, logoutAdmin } from './api.ts'
import {
  createAuthSession,
  type AuthSession,
} from './session.ts'
import { AuthContext } from './authContext.ts'

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSession] = useState<AuthSession | null>(null)
  const [isChecking, setIsChecking] = useState(true)

  useEffect(() => {
    let isMounted = true

    getCurrentAdminSession()
      .then((response) => {
        if (!isMounted) {
          return
        }

        setSession(createAuthSession(response))
      })
      .catch(() => {
        if (!isMounted) {
          return
        }

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
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const response = await loginAdmin({ username, password })
    setSession(createAuthSession(response))
    setIsChecking(false)
  }, [])

  const logout = useCallback(async () => {
    const currentSession = session
    setSession(null)
    setIsChecking(false)
    if (currentSession !== null) {
      try {
        await logoutAdmin(currentSession.csrfToken)
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
