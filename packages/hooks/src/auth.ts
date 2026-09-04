import { get, post } from './http'

export type AuthUser = {
  id: number | string
  username: string
  realname?: string
  tenant?: number | string
}

export async function login(username: string, password: string) {
  return post<{ ok: boolean; user: AuthUser }>('/api/auth/login', {
    username,
    password,
  })
}

export async function fetchMe() {
  return get<{ user: AuthUser }>('/api/auth/me')
}

export async function logout() {
  return post<{ ok: boolean }>('/api/auth/logout', {})
}
