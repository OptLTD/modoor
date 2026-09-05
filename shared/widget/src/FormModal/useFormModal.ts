import { computed, reactive, ref, watch } from 'vue'
import {
  appToast,
  fetchInputSchema,
  upsertRecords,
  type SchemaField,
} from '@modoor/hooks'
import {
  formVisibleFields,
  isEmptyValue,
  isFieldEditable,
  isMultiple,
  isOnlyDate,
  isRequired,
  normalizeReferDict,
  type FormMode,
  type ReferDict,
} from '@modoor/hooks'
import {
  assignFieldPayload,
  fieldKey,
  formFieldDefault,
  injectRowIdentity,
  rowUUKey,
  t,
} from '@modoor/hooks'
import {
  fieldSelectOptions,
  isDateField,
  isFullRowField,
  isNumericFormField,
  isOptionalField,
  isRelationField,
  isSerialField,
  isTextareaField,
} from './fieldKinds'

export type FormModalProps = {
  open: boolean
  model: string
  using?: string
  fields?: SchemaField[]
  mode: FormMode
  row?: Record<string, unknown> | null
  /** 为 true 时校验后只回传 payload，不写库 */
  defer?: boolean
}

export type FormModalEmit = {
  (e: 'close'): void
  (e: 'saved'): void
  (e: 'apply', payload: Record<string, unknown>): void
}

export function useFormModal(props: FormModalProps, emit: FormModalEmit) {
  const saving = ref(false)
  const error = ref('')
  const form = reactive<Record<string, string | string[]>>({})
  const inputFields = ref<SchemaField[] | null>(null)
  const inputValues = ref<Record<string, unknown> | null>(null)
  const inputRefers = ref<ReferDict>({})

  const using = computed(() => props.using || 'default')

  const formFields = computed(() =>
    formVisibleFields(inputFields.value?.length ? inputFields.value : props.fields || []),
  )

  function canEdit(f: SchemaField) {
    return isFieldEditable(f, props.mode)
  }

  function optionsOf(f: SchemaField) {
    return fieldSelectOptions(f, inputRefers.value)
  }

  function resetForm() {
    error.value = ''
    const source =
      props.mode === 'edit'
        ? { ...(props.row || {}), ...(inputValues.value || {}) }
        : inputValues.value
    for (const f of formFields.value) {
      const fk = fieldKey(f)
      form[fk] = formFieldDefault(source, f)
    }
    if (props.mode === 'create' && props.row) {
      for (const f of formFields.value) {
        const fk = fieldKey(f)
        const raw = props.row[fk] ?? props.row[`basic.${f.field}`]
        if (raw != null && String(raw).trim()) {
          form[fk] = String(raw)
        }
      }
    }
  }

  async function loadInputFields() {
    try {
      const scene = props.mode === 'create' ? 'INSERT' : 'DETAIL'
      const uukey = props.mode === 'edit' ? rowUUKey(props.row) : undefined
      const res = await fetchInputSchema(props.model, using.value, scene, uukey)
      inputFields.value = res.input?.fields || []
      inputValues.value = res.input?.values ?? null
      inputRefers.value = normalizeReferDict(res.input?.refers)
    } catch (e) {
      inputFields.value = props.fields?.length ? props.fields : null
      inputValues.value = null
      inputRefers.value = {}
      if (!inputFields.value?.length) {
        error.value = e instanceof Error ? e.message : String(e)
      }
    }
  }

  function validate(): string | null {
    for (const f of formFields.value) {
      if (!isRequired(f)) continue
      if (isEmptyValue(form[fieldKey(f)])) {
        if (props.mode === 'create' && isSerialField(f)) continue
        return t('widget.fillRequired', { label: f.label || f.field })
      }
    }
    return null
  }

  async function save() {
    const msg = validate()
    if (msg) {
      error.value = msg
      return
    }
    saving.value = true
    error.value = ''
    try {
      const payload: Record<string, unknown> = {}
      for (const f of formFields.value) {
        const fk = fieldKey(f)
        const raw = form[fk] ?? (isMultiple(f) ? [] : '')
        if (!canEdit(f)) {
          if (props.mode === 'edit') assignFieldPayload(payload, f, raw)
          continue
        }
        assignFieldPayload(payload, f, raw)
      }
      if (props.mode === 'edit') {
        injectRowIdentity(payload, props.row)
      }

      if (props.defer) {
        emit('apply', payload)
        emit('close')
        return
      }

      await upsertRecords(props.model, [payload], using.value)
      emit('saved')
      emit('close')
    } catch (e: unknown) {
      appToast(e instanceof Error ? e.message : String(e), 'error')
    } finally {
      saving.value = false
    }
  }

  watch(
    () => [props.open, props.mode, props.model, rowUUKey(props.row)] as const,
    async ([open]) => {
      if (!open) return
      await loadInputFields()
      resetForm()
    },
  )

  return {
    saving,
    error,
    form,
    formFields,
    canEdit,
    optionsOf,
    save,
    fieldKey,
    isRequired,
    isMultiple,
    isOnlyDate,
    isRelation: isRelationField,
    isOptional: isOptionalField,
    isNumeric: isNumericFormField,
    isDate: isDateField,
    isSerial: isSerialField,
    isTextarea: isTextareaField,
    isFullRow: isFullRowField,
  }
}
