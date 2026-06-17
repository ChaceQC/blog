import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from 'react'

import { setAuthRefreshHandler } from '../../api/client.ts'
import {
  getCurrentAdminSession,
  loginAdmin,
  logoutAdmin,
  refreshAdmin,
} from './api.ts'
import { createAuthSession, type AuthSession } from './session.ts'
import { AuthContext } from './authContext.ts'

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSession] = useState<AuthSession | null>(null)
  const [isChecking, setIsChecking] = useState(true)
  const isMountedRef = useRef(false)
  const refreshPromiseRef = useRef<Promise<boolean> | null>(null)

  const refreshSession = useCallback(async (): Promise<boolean> => {
    if (refreshPromiseRef.current !== null) {
      return refreshPromiseRef.current
    }

    const refreshPromise = refreshAdmin()
      .then((response) => {
        if (isMountedRef.current) {
          setSession(createAuthSession(response))
          setIsChecking(false)
        }
        return true
      })
      .catch(() => {
        if (isMountedRef.current) {
          setSession(null)
          setIsChecking(false)
        }
        return false
      })
      .finally(() => {
        refreshPromiseRef.current = null
      })

    refreshPromiseRef.current = refreshPromise
    return refreshPromise
  }, [])

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  useEffect(() => {
    setAuthRefreshHandler(refreshSession)
    return () => setAuthRefreshHandler(null)
  }, [refreshSession])

  useEffect(() => {
    let isCancelled = false

    async function checkSession() {
      try {
        const response = await getCurrentAdminSession()
        if (!isCancelled) {
          setSession(createAuthSession(response))
        }
      } catch {
        if (!isCancelled) {
          setSession(null)
        }
      } finally {
        if (!isCancelled) {
          setIsChecking(false)
        }
      }
    }

    void checkSession()

    return () => {
      isCancelled = true
    }
  }, [refreshSession])

  useEffect(() => {
    if (session === null) {
      return undefined
    }

    const refreshDelay = Math.max(session.expiresAt - Date.now() - 60_000, 10_000)
    const timeoutId = window.setTimeout(() => {
      void refreshSession()
    }, refreshDelay)

    return () => window.clearTimeout(timeoutId)
  }, [refreshSession, session])

  useEffect(() => {
    if (session === null) {
      return undefined
    }

    const currentSession = session

    function refreshIfNeeded() {
      if (currentSession.expiresAt - Date.now() < 60_000) {
        void refreshSession()
      }
    }

    window.addEventListener('focus', refreshIfNeeded)
    document.addEventListener('visibilitychange', refreshIfNeeded)

    return () => {
      window.removeEventListener('focus', refreshIfNeeded)
      document.removeEventListener('visibilitychange', refreshIfNeeded)
    }
  }, [refreshSession, session])

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
        // Local logout wins; stale server state is cleared by the next login.
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
