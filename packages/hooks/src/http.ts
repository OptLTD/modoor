export async function post<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body ?? {}),
  })
  if (res.status === 401) {
    redirectToLogin()
    throw new Error('login required')
  }
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  return res.json() as Promise<T>
}

export async function get<T>(url: string): Promise<T> {
  const res = await fetch(url, {
    method: 'GET',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (res.status === 401) {
    redirectToLogin()
    throw new Error('login required')
  }
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  return res.json() as Promise<T>
}

/** Login URL — same-origin `/login` when behind API proxy; optional VITE_SHELL_URL. */
export function shellLoginUrl(next?: string): string {
  const shell = (import.meta as ImportMeta & { env: Record<string, string> }).env
    ?.VITE_SHELL_URL
  const base = (shell || '').replace(/\/$/, '')
  const target = next || `${location.pathname}${location.search}`
  const q = `next=${encodeURIComponent(target.startsWith('http') ? target : location.href)}`
  if (base) return `${base}/login?${q}`
  return `/login?${q}`
}

function redirectToLogin() {
  if (location.pathname.startsWith('/login')) return
  location.href = shellLoginUrl()
}
