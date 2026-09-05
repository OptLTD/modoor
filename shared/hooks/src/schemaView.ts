import type { SchemaField } from './record'
import type { ReferDict } from './fieldMeta'

/** 表格 / sheet 视图的 schema 描述 */
export type SchemaTable = {
  model: string
  using?: string
  title?: string
  fields: SchemaField[]
  sticky?: string[]
  refers?: ReferDict
  clicks?: { uukey: string; label?: string; action?: string; group?: string; seqno?: number }[]
  createDefaults?: Record<string, unknown>
  request?: SchemaRequest
}

/** 列表 / sheet 请求参数 */
export type SchemaRequest = {
  page?: number
  size?: number
  query?: Record<string, unknown>
  order?: { field: string; order: string }
}
