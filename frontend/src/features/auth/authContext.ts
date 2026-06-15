import { createContext } from 'react'

import type { AuthSession } from './session.ts'

export type AuthContextValue = {
  session: AuthSession | null
  isChecking: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
