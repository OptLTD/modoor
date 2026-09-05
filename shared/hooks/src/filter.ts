import type { SchemaField } from './record'

export type { FilterDraft } from './recordPayload'

/** 按字段类型返回可选运算符（与后端 field:OP 对齐） */
export function filterOps(f: SchemaField): { value: string; label: string }[] {
  const t = String(f.ftype || '').toUpperCase()
  const ALL = { value: 'ALL', label: '全部' }
  if (t === 'OPTIONAL' || t === 'RELATION') {
    return [
      ALL,
      { value: 'IN', label: '包含任一' },
      { value: 'EQ', label: '等于' },
      { value: 'NE', label: '不等于' },
      { value: 'NIL', label: '为空' },
      { value: 'NNL', label: '不为空' },
    ]
  }
  if (t === 'NUMERIC' || t === 'EXPENSE' || t === 'INTEGER') {
    return [
      ALL,
      { value: 'EQ', label: '等于' },
      { value: 'GT', label: '大于' },
      { value: 'GE', label: '大于等于' },
      { value: 'LT', label: '小于' },
      { value: 'LE', label: '小于等于' },
      { value: 'BTW', label: '介于' },
      { value: 'NIL', label: '为空' },
      { value: 'NNL', label: '不为空' },
    ]
  }
  if (t === 'DATETIME') {
    return [
      ALL,
      { value: 'EQ', label: '等于' },
      { value: 'GT', label: '晚于' },
      { value: 'LT', label: '早于' },
      { value: 'BTW', label: '介于' },
      { value: 'NIL', label: '为空' },
      { value: 'NNL', label: '不为空' },
    ]
  }
  return [
    ALL,
    { value: 'IN', label: '包含任一' },
    { value: 'LIKE', label: '包含' },
    { value: 'EQ', label: '等于' },
    { value: 'NE', label: '不等于' },
    { value: 'NIL', label: '为空' },
    { value: 'NNL', label: '不为空' },
  ]
}

export function defaultOp(f: SchemaField): string {
  return filterOps(f)[0]?.value || 'LIKE'
}

export function showValue(op: string): boolean {
  return op !== 'NIL' && op !== 'NNL'
}

export function needsValue(op: string): boolean {
  return op !== 'NIL' && op !== 'NNL' && op !== 'ALL'
}

export function needsValue2(op: string): boolean {
  return op === 'BTW'
}

export function isDraftActive(d: { op: string; value: string; value2: string } | undefined): boolean {
  if (!d || !d.op) return false
  if (d.op === 'ALL') return false
  if (d.op === 'NIL' || d.op === 'NNL') return true
  if (d.op === 'BTW') return !!d.value && !!d.value2
  return String(d.value ?? '').trim() !== ''
}
