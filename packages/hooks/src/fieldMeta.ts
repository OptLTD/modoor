import type { SchemaField } from './record'
import { formatDateTimeDisplay, pickFieldValue } from './recordPayload'

export type ReferDict = Record<string, Record<string, unknown>[]>
export type FormMode = 'create' | 'edit'

function extraStr(f: SchemaField, key: string, fallback = '') {
  const v = f.extra?.[key]
  if (v == null || v === '') return fallback
  return String(v)
}

function extraBool(f: SchemaField, key: string) {
  const v = f.extra?.[key]
  return v === true || v === 1 || v === '1' || String(v).toLowerCase() === 'true'
}

function ftypeOf(f: SchemaField) {
  return String(f.ftype || '').toUpperCase()
}

export function referGet(obj: Record<string, unknown> | null | undefined, key: string): unknown {
  if (!obj || !key) return undefined
  if (key in obj) return obj[key]
  const tail = key.split('.').pop()
  if (tail && tail in obj) return obj[tail]
  return undefined
}

export function fieldRefer(f: SchemaField): { using: string; keyby: string; txtby: string } | null {
  const ft = ftypeOf(f)
  if (f.refer?.using) {
    return {
      using: f.refer.using,
      keyby: f.refer.keyby || (ft === 'RELATION' ? 'basic.uukey' : 'uukey'),
      txtby: f.refer.txtby || (ft === 'RELATION' ? 'basic.name' : 'label'),
    }
  }
  if (ft === 'RELATION') {
    const using = String(f.extra?.relation || '')
    if (!using) return null
    return {
      using,
      keyby: String(f.extra?.dataKey || 'basic.uukey'),
      txtby: String(f.extra?.textKey || 'basic.name'),
    }
  }
  if (ft === 'OPTIONAL') {
    return { using: f.uukey, keyby: 'uukey', txtby: 'label' }
  }
  return null
}

export function convertReferValue(f: SchemaField, rowValue: unknown, refers?: ReferDict): string {
  const refer = fieldRefer(f)
  if (!refer?.using || rowValue == null || rowValue === '') {
    return rowValue == null ? '' : String(rowValue)
  }
  const dict = refers?.[refer.using]
  if (!Array.isArray(dict) || !dict.length) return String(rowValue)
  const hit = dict.find((x) => String(referGet(x, refer.keyby) ?? '') === String(rowValue))
  return hit ? String(referGet(hit, refer.txtby) ?? rowValue) : String(rowValue)
}

export function displayFieldValue(
  row: Record<string, unknown>,
  f: SchemaField,
  ctx?: { refers?: ReferDict },
): string {
  const raw = pickFieldValue(row, f)
  const ft = ftypeOf(f)
  if (ft === 'DATETIME') return formatDateTimeDisplay(raw)
  if (ft === 'OPTIONAL' || ft === 'RELATION') {
    return convertReferValue(f, raw, ctx?.refers)
  }
  if (raw == null) return ''
  return String(raw)
}

export function isNumericField(f: SchemaField) {
  const t = ftypeOf(f)
  return t === 'NUMERIC' || t === 'EXPENSE' || t === 'INTEGER'
}

export function referOptions(
  f: SchemaField,
  refers?: ReferDict,
): { label: string; value: string }[] {
  const refer = fieldRefer(f)
  if (refer?.using) {
    const dict = refers?.[refer.using] || []
    return dict
      .map((item) => {
        const value = String(referGet(item, refer.keyby) ?? '')
        const label = String(referGet(item, refer.txtby) ?? value)
        return { value, label }
      })
      .filter((o) => o.value)
  }
  const raw = (f.options ||
    (f.extra?.options as { label?: string; value?: string; uukey?: string }[] | undefined)) as
    | { label?: string; value?: string; uukey?: string }[]
    | undefined
  return (raw || [])
    .map((o) => ({
      label: String(o.label || o.uukey || o.value || ''),
      value: String(o.uukey ?? o.value ?? ''),
    }))
    .filter((o) => o.value)
}

export function mergeRefers(schemaRefers?: ReferDict, resultRefers?: ReferDict): ReferDict {
  return { ...(schemaRefers || {}), ...(resultRefers || {}) }
}

export function normalizeReferDict(raw?: Record<string, unknown> | ReferDict): ReferDict {
  const out: ReferDict = {}
  if (!raw) return out
  for (const [k, v] of Object.entries(raw)) {
    if (Array.isArray(v)) out[k] = v as Record<string, unknown>[]
  }
  return out
}

/** 按 schema.sticky 顺序排列可见列 */
export function applyStickyOrder(keys: string[], sticky: string[]): string[] {
  const set = new Set(sticky)
  const head = sticky.filter((k) => keys.includes(k))
  const rest = keys.filter((k) => !set.has(k))
  return [...head, ...rest]
}

export function isSortableField(f: SchemaField) {
  return !!(f.uukey || f.index)
}

/** 排序请求用逻辑键（uukey） */
export function sortIndexField(f: SchemaField) {
  return f.uukey || f.index || ''
}

export function isImplicit(f: SchemaField) {
  return extraBool(f, 'implicit')
}

export function isRequired(f: SchemaField) {
  return extraBool(f, 'required')
}

export function isMultiple(f: SchemaField) {
  return extraBool(f, 'multiple')
}

export function editableMode(f: SchemaField) {
  return extraStr(f, 'editable', 'ALWAYS').toUpperCase()
}

export function disabledMode(f: SchemaField) {
  return extraStr(f, 'disabled', 'NEVER').toUpperCase()
}

export function isFieldEditable(f: SchemaField, mode: FormMode) {
  const disabled = disabledMode(f)
  if (disabled === 'ALWAYS' || disabled === 'UPSERT') return false
  if (mode === 'create' && disabled === 'INSERT') return false
  if (mode === 'edit' && disabled === 'UPDATE') return false

  switch (editableMode(f)) {
    case 'NEVER':
      return false
    case 'INSERT':
      return mode === 'create'
    case 'UPDATE':
      return mode === 'edit'
    case 'UPSERT':
    case 'ALWAYS':
    case '':
      return true
    default:
      return true
  }
}

export function isLongTextField(f: SchemaField) {
  const dt = extraStr(f, 'dataType').toUpperCase()
  if (dt === 'LONGTEXT' || dt === 'RICHTEXT') return true
  return ftypeOf(f) === 'LONGTEXT'
}

/** 表单可见字段：shown≠false，非隐式；长文本排后 */
export function formVisibleFields(fields: SchemaField[]) {
  const visible = fields.filter(
    (f) => f.field && f.field !== 'model' && f.shown !== false && !isImplicit(f),
  )
  const normal: SchemaField[] = []
  const longText: SchemaField[] = []
  for (const f of visible) {
    if (isLongTextField(f)) longText.push(f)
    else normal.push(f)
  }
  return [...normal, ...longText]
}

export function isEmptyValue(v: string | string[] | undefined | null) {
  if (v == null) return true
  if (Array.isArray(v)) return v.length === 0
  return !String(v).trim()
}

export function isOnlyDate(f: SchemaField) {
  const dt = extraStr(f, 'datetime').toUpperCase()
  const dataType = extraStr(f, 'dataType').toUpperCase()
  return dt === 'ONLYDATE' || dataType === 'ONLYDATE'
}
