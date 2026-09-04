import { post } from './http'

export type SchemaField = {
  uukey: string
  field: string
  label: string
  ftype: string
  group: string
  seqno?: number
  index?: string
  width?: number
  shown?: boolean
  refer?: { using?: string; keyby?: string; txtby?: string }
  options?: { label?: string; value?: string; uukey?: string }[]
  extra?: Record<string, unknown>
}

export type SchemaClick = {
  uukey: string
  label?: string
  action?: string
  ctype?: string
  seqno?: number
  group?: string
}

export type SchemaTable = {
  model: string
  using?: string
  title?: string
  sticky?: string[]
  fields: SchemaField[]
  clicks?: SchemaClick[]
  refers?: Record<string, unknown>
  /** 新建表单预填（与 FormModal create + row 配合） */
  createDefaults?: Record<string, unknown>
  request?: {
    page?: number
    size?: number
    query?: Record<string, unknown>
    order?: { field: string; order: string }
  }
}

export type SearchResult = {
  page?: number
  size?: number
  values?: Record<string, unknown>[]
  count?: number
  refers?: Record<string, unknown>
  totals?: Record<string, unknown> | null
}

export async function fetchSchema(model: string, using = 'default', scene = 'SEARCH') {
  return post<{
    model: string
    using: string
    scene: string
    table: SchemaTable
  }>('/api/record/schema', { model, using, scene, page: 1, size: 50 })
}

export async function searchRecords(
  model: string,
  using = 'default',
  page = 1,
  size = 50,
  opts: { query?: Record<string, unknown>; order?: { field: string; order: string } } = {},
) {
  return post<SearchResult>('/api/record/search', {
    model,
    using,
    scene: 'SEARCH',
    page,
    size,
    query: opts.query,
    order: opts.order,
  })
}

export async function fetchInputSchema(
  model: string,
  using = 'default',
  scene = 'DETAIL',
  uukey?: string,
) {
  return post<{
    input: {
      title?: string
      fields?: SchemaField[]
      values?: Record<string, unknown>
      refers?: Record<string, unknown>
    }
  }>('/api/record/input', { model, using, scene, ...(uukey ? { uukey } : {}) })
}

export async function upsertRecords(
  model: string,
  batch: Record<string, unknown>[],
  using = 'default',
) {
  return post<{ records: unknown[] }>('/api/record/upsert', {
    model,
    using,
    scene: 'UPDATE',
    batch,
  })
}

export async function deleteRecords(model: string, keys: string[]) {
  return post<{ ok: boolean }>('/api/record/delete', { model, keys })
}

/** Sheet 新建行编号：后端可空 uukey 自生成时返回空串占位 */
export async function allocSerials(
  _model: string,
  count: number,
  _kind?: string,
): Promise<{ codes: string[] }> {
  return { codes: Array.from({ length: Math.max(0, count) }, () => '') }
}

/** Sheet 公式回填：当前引擎未实现 */
export async function autofillRecord(
  _model: string,
  _value: Record<string, unknown>,
  _using = 'default',
): Promise<{ data: Record<string, unknown> }> {
  return { data: {} }
}

export async function autofillBatch(
  _model: string,
  _batch: Record<string, unknown>[],
  _using = 'default',
): Promise<{ data: Record<string, unknown>[] }> {
  return { data: [] }
}
