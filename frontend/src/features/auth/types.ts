export type AuthUser = {
  id: number
  username: string
  display_name: string | null
  roles: string[]
  permissions: string[]
}

export type AuthSessionResponse = {
  user: AuthUser
  csrf_token: string
  expires_in: number
}

export type LoginPayload = {
  username: string
  password: string
}
