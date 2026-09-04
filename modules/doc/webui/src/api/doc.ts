import { get, post } from '@modoor/hooks'

export type DocAsset = {
  id: string
  title: string
  filename: string
  mime_type: string
  size_bytes: number
  type: string
  name: string
  tags: string[]
  note?: string
  text?: string
  has_text?: boolean
  text_truncated?: boolean
  ext?: string
  created_at?: string | null
  updated_at?: string | null
}

export type TagItem = { tag: string; count: number }

export async function listAssets(params?: { q?: string; tag?: string; limit?: number }) {
  const qs = new URLSearchParams()
  if (params?.q) qs.set('q', params.q)
  if (params?.tag) qs.set('tag', params.tag)
  if (params?.limit) qs.set('limit', String(params.limit))
  const suffix = qs.toString() ? `?${qs}` : ''
  return get<{ items: DocAsset[]; count: number }>(`/api/doc/assets${suffix}`)
}

export async function getAsset(id: string) {
  return get<{ asset: DocAsset }>(`/api/doc/assets/${encodeURIComponent(id)}`)
}

export async function listTags() {
  return get<{ items: TagItem[]; count: number }>('/api/doc/tags')
}

export async function uploadAsset(file: File, opts?: { title?: string; tags?: string[]; note?: string }) {
  const body = new FormData()
  body.append('file', file)
  if (opts?.title) body.append('title', opts.title)
  if (opts?.tags?.length) body.append('tags', JSON.stringify(opts.tags))
  if (opts?.note) body.append('note', opts.note)
  const res = await fetch('/api/doc/assets', {
    method: 'POST',
    credentials: 'include',
    body,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<{ ok: boolean; asset: DocAsset }>
}

export async function createTextAsset(body: {
  title: string
  text: string
  tags?: string[]
  note?: string
  filename?: string
}) {
  return post<{ ok: boolean; asset: DocAsset }>('/api/doc/assets/text', body)
}

export async function updateAsset(
  id: string,
  body: { title?: string; tags?: string[]; note?: string; text?: string },
) {
  const res = await fetch(`/api/doc/assets/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<{ ok: boolean; asset: DocAsset }>
}

export async function deleteAsset(id: string) {
  const res = await fetch(`/api/doc/assets/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export function contentUrl(id: string, download = false) {
  const qs = download ? '?download=1' : ''
  return `/api/doc/assets/${encodeURIComponent(id)}/content${qs}`
}

export async function fetchContentBlob(id: string) {
  const res = await fetch(contentUrl(id), { credentials: 'include' })
  if (!res.ok) throw new Error(await res.text())
  return res.blob()
}
