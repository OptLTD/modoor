import type { SchemaField } from './record'

export type FilterDraft = {
  op: string
  value: string
  value2: string
}

export function fieldKey(f: SchemaField): string {
  if (f.uukey) return f.uukey
  if (f.index) return f.index
  if (f.group && f.field) return `${f.group}.${f.field}`
  if (f.field) return `basic.${f.field}`
  return ''
}

export function rowUUKey(row: Record<string, unknown> | null | undefined): string {
  if (!row) return ''
  const direct = row.uukey ?? row['basic.uukey']
  if (direct != null && String(direct).trim() !== '') return String(direct).trim()
  return ''
}

export function pickFieldValue(row: Record<string, unknown> | null | undefined, f: SchemaField): unknown {
  if (!row) return ''
  const key = fieldKey(f)
  if (key in row) return row[key]
  if (f.index && f.index in row) return row[f.index]
  if (f.field && f.field in row) return row[f.field]
  const nested = row[f.group]
  if (nested && typeof nested === 'object') {
    return (nested as Record<string, unknown>)[f.field]
  }
  return undefined
}

export function formatDateTimeDisplay(raw: unknown, onlyDate = false): string {
  if (raw == null || raw === '') return ''
  const s = String(raw)
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) {
    if (onlyDate) return s.slice(0, 10)
    return s.includes('T') ? s.replace('T', ' ').slice(0, 19) : s.slice(0, 10)
  }
  return s
}

export function formatDateInputValue(raw: unknown): string {
  if (raw == null || raw === '') return ''
  return String(raw).slice(0, 10)
}

export function formatDateTimeInputValue(raw: unknown): string {
  if (raw == null || raw === '') return ''
  const s = String(raw).replace(' ', 'T')
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(s)) return s.slice(0, 16)
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return `${s.slice(0, 10)}T00:00`
  return s
}

export function normalizeDateTimeStoreValue(raw: string, onlyDate: boolean): string {
  const s = String(raw || '').trim()
  if (!s) return ''
  if (onlyDate) return s.slice(0, 10)
  return s.includes('T') ? s : s.replace(' ', 'T')
}

function payloadScalar(value: string | string[]): string | string[] {
  if (Array.isArray(value)) return value.map(String).filter((s) => s.trim())
  return String(value ?? '')
}

/** 表单初始值 */
export function formFieldDefault(
  row: Record<string, unknown> | null | undefined,
  f: SchemaField,
): string | string[] {
  const multi = !!(f.extra?.multiple === true || f.extra?.multiple === 'true')
  const raw = pickFieldValue(row, f)
  if (raw == null || raw === '') return multi ? [] : ''
  if (String(f.ftype).toUpperCase() === 'DATETIME' && !Array.isArray(raw)) {
    const onlyDate =
      String(f.extra?.datetime || '').toUpperCase() === 'ONLYDATE' ||
      String(f.extra?.dataType || '').toUpperCase() === 'ONLYDATE'
    return onlyDate ? formatDateInputValue(raw) : formatDateTimeInputValue(raw)
  }
  if (multi) {
    if (Array.isArray(raw)) return raw.map(String)
    return String(raw)
      .split(/[,\n]/)
      .map((s) => s.trim())
      .filter(Boolean)
  }
  return Array.isArray(raw) ? raw.join(',') : String(raw)
}

export function assignFieldPayload(
  payload: Record<string, unknown>,
  f: SchemaField,
  value: string | string[],
) {
  let v: unknown = payloadScalar(value)
  if (String(f.ftype).toUpperCase() === 'DATETIME') {
    const onlyDate =
      String(f.extra?.datetime || '').toUpperCase() === 'ONLYDATE' ||
      String(f.extra?.dataType || '').toUpperCase() === 'ONLYDATE'
    v = normalizeDateTimeStoreValue(String(v ?? ''), onlyDate)
  }
  const key = fieldKey(f)
  if (key) payload[key] = v
  if (f.group === 'basic' || !f.group) {
    if (f.field) payload[f.field] = v
  }
}

export function injectRowIdentity(
  payload: Record<string, unknown>,
  row: Record<string, unknown> | null | undefined,
) {
  const uk = rowUUKey(row)
  if (!uk) return
  payload.uukey = uk
  payload['basic.uukey'] = uk
}

/** Sheet 行 → upsert batch 项 */
export function rowToUpsertPayload(
  row: Record<string, string>,
  fields: SchemaField[],
): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  const uk = row.uukey?.trim()
  if (uk) injectRowIdentity(out, { uukey: uk })

  for (const f of fields) {
    const fk = fieldKey(f)
    const raw = row[fk] ?? row[f.field] ?? ''
    const v = raw == null ? '' : String(raw)
    if (!v.trim() && f.field !== 'uukey') continue
    assignFieldPayload(out, f, v)
  }
  return out
}

/** 将列筛选草稿转为 search query（field / field:OP） */
export function buildListQuery(
  applied: Record<string, FilterDraft>,
  fields: SchemaField[],
): Record<string, unknown> | undefined {
  const q: Record<string, unknown> = {}
  for (const [fk, draft] of Object.entries(applied)) {
    if (!draft?.op) continue
    const f = fields.find((x) => fieldKey(x) === fk)
    const key = f ? fieldKey(f) : fk
    let op = draft.op
    if (op === 'ALL') continue
    // 前端 GE/LE → 后端 GTE/LTE
    if (op === 'GE') op = 'GTE'
    if (op === 'LE') op = 'LTE'
    if (op === 'NIL' || op === 'NNL') {
      // 后端仅识别 NIL：true=为空，false=不为空
      q[`${key}:NIL`] = op === 'NIL'
      continue
    }
    if (op === 'IN') {
      const arr = String(draft.value ?? '')
        .split(/[,\n]/)
        .map((s) => s.trim())
        .filter(Boolean)
      if (arr.length) q[`${key}:IN`] = arr
      continue
    }
    if (!String(draft.value ?? '').trim() && op !== 'EQ') continue
    if (op === 'BTW') {
      if (!draft.value || !draft.value2) continue
      q[`${key}:BTW`] = [draft.value, draft.value2]
      continue
    }
    if (op === 'EQ') {
      q[key] = draft.value
      continue
    }
    q[`${key}:${op}`] = draft.value
  }
  return Object.keys(q).length ? q : undefined
}

export function mergeListQuery(
  applied?: Record<string, unknown>,
  fixed?: Record<string, unknown>,
): Record<string, unknown> | undefined {
  const merged = { ...(applied || {}), ...(fixed || {}) }
  return Object.keys(merged).length ? merged : undefined
}
