import { get, post } from './http'

export type AuthTenant = {
  id: number | string
  name: string
}

export type AuthUser = {
  id: number | string
  uukey?: string
  username: string
  realname?: string
  tenant?: number | string
  current?: number | string | null
  base_id?: number | string
  tenants?: AuthTenant[]
}

export async function login(username: string, password: string) {
  return post<{ ok: boolean; user: AuthUser }>('/api/auth/login', {
    username,
    password,
  })
}

export async function fetchProfile() {
  return get<{ user: AuthUser }>('/api/auth/profile')
}

/** @deprecated use fetchProfile */
export const fetchMe = fetchProfile

export async function switchTenant(tenantId: number | string) {
  return post<{ ok: boolean; user: AuthUser }>('/api/auth/switch', {
    tenant_id: Number(tenantId),
  })
}

export async function logout() {
  return post<{ ok: boolean }>('/api/auth/logout', {})
}
