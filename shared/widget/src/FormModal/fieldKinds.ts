import type { SchemaField } from '@modoor/hooks'
import {
  isLongTextField,
  isNumericField,
  referOptions,
  type ReferDict,
} from '@modoor/hooks'

export function isRelationField(f: SchemaField) {
  return String(f.ftype).toUpperCase() === 'RELATION'
}

export function isOptionalField(f: SchemaField) {
  return String(f.ftype).toUpperCase() === 'OPTIONAL'
}

export function isDateField(f: SchemaField) {
  return String(f.ftype).toUpperCase() === 'DATETIME'
}

export function isSerialField(f: SchemaField) {
  return String(f.ftype).toUpperCase() === 'SERIALNO' || f.field === 'uukey'
}

export function isNumericFormField(f: SchemaField) {
  return isNumericField(f)
}

export function isTextareaField(f: SchemaField) {
  return isLongTextField(f) || f.field === 'remark' || f.field === 'note'
}

export function isFullRowField(f: SchemaField) {
  return isTextareaField(f)
}

/** Select 选项：优先 refers，回退 field.options */
export function fieldSelectOptions(
  f: SchemaField,
  refers?: ReferDict,
): { label: string; value: string }[] {
  const fromRefer = referOptions(f, refers)
  if (fromRefer.length) return fromRefer
  const raw = (f.options || f.extra?.options || []) as {
    label?: string
    value?: string
    uukey?: string
  }[]
  return raw
    .map((o) => {
      const value = String(o.uukey ?? o.value ?? '')
      const label = String(o.label || value)
      return { label, value }
    })
    .filter((o) => o.value)
}
