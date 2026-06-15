import { useState, type FormEvent } from 'react'
import { LockKeyhole, LogIn, UserRound } from 'lucide-react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { ApiError } from '../../api/client.ts'
import { useAuth } from '../../features/auth/useAuth.ts'

type LoginLocationState = {
  from?: string
}

export function AdminLoginPage() {
  const { isChecking, login, session } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const state = location.state as LoginLocationState | null
  const redirectTo = state?.from ?? '/admin'

  if (isChecking) {
    return <main className="admin-auth-loading">正在校验登录状态</main>
  }

  if (session !== null) {
    return <Navigate to={redirectTo} replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      await login(username, password)
      navigate(redirectTo, { replace: true })
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        setError('用户名或密码不正确')
      } else {
        setError('登录暂时不可用')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="login-shell">
      <section className="login-panel">
        <div className="admin-heading">
          <span>后台登录</span>
          <h1>进入管理台</h1>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label>
            <span>用户名</span>
            <div className="field-control">
              <UserRound size={17} strokeWidth={1.8} aria-hidden="true" />
              <input
                autoComplete="username"
                name="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
              />
            </div>
          </label>

          <label>
            <span>密码</span>
            <div className="field-control">
              <LockKeyhole size={17} strokeWidth={1.8} aria-hidden="true" />
              <input
                autoComplete="current-password"
                name="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>
          </label>

          {error && <p className="form-error">{error}</p>}

          <button className="text-button login-submit" disabled={isSubmitting}>
            <LogIn size={17} strokeWidth={1.9} aria-hidden="true" />
            {isSubmitting ? '登录中' : '登录'}
          </button>
        </form>
      </section>
    </main>
  )
}
