import type { SchemaField } from '@modoor/hooks'
import { fieldKey } from '@modoor/hooks'
import { defaultColWidth } from './fieldUtils'

export function colWidthStorageKey(model: string, fieldId: string) {
  return `modoor.sheetColWidth.${model}.${fieldId}`
}

export function loadColWidths(
  model: string,
  fields: SchemaField[],
  colWidths: Record<string, number>,
) {
  for (const f of fields) {
    if (!f.field) continue
    const fk = fieldKey(f)
    const raw = localStorage.getItem(colWidthStorageKey(model, fk))
    if (!raw) continue
    const n = Number(raw)
    if (Number.isFinite(n) && n >= 40) colWidths[fk] = n
  }
}

export function saveColWidth(
  model: string,
  fk: string,
  width: number,
  colWidths: Record<string, number>,
) {
  const w = Math.max(40, Math.round(width))
  colWidths[fk] = w
  localStorage.setItem(colWidthStorageKey(model, fk), String(w))
}

export function resolveColWidth(f: SchemaField, colWidths: Record<string, number>) {
  const fk = fieldKey(f)
  if (colWidths[fk]) return colWidths[fk]
  return defaultColWidth(f)
}
