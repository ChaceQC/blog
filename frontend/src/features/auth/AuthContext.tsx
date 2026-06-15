import {
  useCallback,
  useMemo,
  useState,
  type PropsWithChildren,
} from 'react'

import { loginAdmin, logoutAdmin } from './api.ts'
import {
  clearAuthSession,
  createAuthSession,
  readAuthSession,
  saveAuthSession,
  type AuthSession,
} from './session.ts'
import { AuthContext } from './authContext.ts'

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSession] = useState<AuthSession | null>(() =>
    readAuthSession(),
  )

  const login = useCallback(async (username: string, password: string) => {
    const tokens = await loginAdmin({ username, password })
    const nextSession = createAuthSession(tokens)
    saveAuthSession(nextSession)
    setSession(nextSession)
  }, [])

  const logout = useCallback(async () => {
    const currentSession = session
    clearAuthSession()
    setSession(null)
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
      login,
      logout,
    }),
    [login, logout, session],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
