export type AuthUser = {
  id: number
  username: string
  display_name: string | null
  roles: string[]
  permissions: string[]
}

export type TokenPair = {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  expires_in: number
  user: AuthUser
}

export type LoginPayload = {
  username: string
  password: string
}
