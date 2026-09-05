import type { SchemaRequest, SchemaTable } from '@modoor/hooks'

export type SheetRow = Record<string, string>

/** jspreadsheet worksheet 实例 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type SheetWorksheet = any

export type SchemaSheetProps = {
  table: SchemaTable
  request?: SchemaRequest
  /** edit=只改已有；import=只建新；默认 edit */
  mode?: 'edit' | 'import'
}

export type RecalcPending = { row: number; col: number; triggerUukey: string }
