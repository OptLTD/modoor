<script setup lang="ts">
import { computed } from 'vue'
import type { SchemaField } from '@modoor/hooks'
import { useI18n } from '@modoor/hooks'
import { useFormModal } from './useFormModal'
import SelectBox from '../SelectBox/SelectBox.vue'

const props = defineProps<{
  open: boolean
  model: string
  using?: string
  fields?: SchemaField[]
  mode: 'create' | 'edit'
  row?: Record<string, unknown> | null
  defer?: boolean
}>()

const emit = defineEmits<{
  close: []
  saved: []
  apply: [Record<string, unknown>]
}>()

const { t } = useI18n()
const heading = computed(() =>
  props.mode === 'create' ? t('widget.formCreate') : t('widget.formEdit'),
)

const {
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
  isRelation,
  isOptional,
  isNumeric,
  isDate,
  isSerial,
  isTextarea,
  isFullRow,
} = useFormModal(props, emit)
</script>

<template>
  <div v-if="open" class="modal-mask" @click.self="emit('close')">
    <div class="modal form-modal">
      <header class="modal-head">
        <strong>{{ heading }}</strong>
        <button type="button" class="link" @click="emit('close')">{{ t('widget.close') }}</button>
      </header>

      <div class="form-modal-body">
        <p v-if="error" class="error">{{ error }}</p>
        <div class="form-grid-2">
          <label
            v-for="f in formFields"
            :key="f.uukey"
            class="field"
            :class="{ full: isFullRow(f) }"
          >
            <span class="field-label">
              {{ f.label || f.field }}
              <span v-if="isRequired(f)" class="req">*</span>
            </span>
            <SelectBox
              v-if="isRelation(f) || isOptional(f)"
              v-model="form[fieldKey(f)]"
              :options="optionsOf(f)"
              :multiple="isMultiple(f)"
              :disabled="!canEdit(f)"
            />
            <input
              v-else-if="isDate(f)"
              v-model="form[fieldKey(f)] as string"
              :type="isOnlyDate(f) ? 'date' : 'datetime-local'"
              :disabled="!canEdit(f)"
            />
            <input
              v-else-if="isNumeric(f)"
              v-model="form[fieldKey(f)] as string"
              type="number"
              class="num"
              :disabled="!canEdit(f)"
            />
            <textarea
              v-else-if="isTextarea(f)"
              v-model="form[fieldKey(f)] as string"
              rows="3"
              :disabled="!canEdit(f)"
            />
            <input
              v-else
              v-model="form[fieldKey(f)] as string"
              type="text"
              :disabled="!canEdit(f)"
              :placeholder="mode === 'create' && isSerial(f) ? t('widget.serialAuto') : ''"
            />
          </label>
        </div>
      </div>

      <div class="modal-actions pad-actions">
        <button type="button" class="btn" @click="emit('close')">{{ t('widget.cancel') }}</button>
        <button type="button" class="btn primary" :disabled="saving" @click="save">
          {{ saving ? t('widget.saving') : defer ? t('widget.applyDefer') : t('widget.save') }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.form-modal {
  width: min(640px, 100%);
  display: flex;
  flex-direction: column;
  max-height: 85vh;
}
.form-modal-body {
  padding: 16px;
  overflow: auto;
  min-height: 0;
  flex: 1;
}
.form-grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 16px;
}
.field {
  display: grid;
  gap: 6px;
  font-size: 0.9rem;
  min-width: 0;
}
.field.full {
  grid-column: 1 / -1;
}
.field-label {
  font-weight: 500;
}
.req {
  color: var(--danger);
  margin-left: 2px;
}
.field input,
.field textarea {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 8px 10px;
  font: inherit;
  background: #fff;
  width: 100%;
}
.field input:disabled,
.field textarea:disabled {
  background: #f8f4eb;
  color: var(--muted);
  cursor: not-allowed;
}
.field textarea {
  resize: vertical;
  min-height: 4.5rem;
  line-height: 1.4;
}
.field .num {
  font-variant-numeric: tabular-nums;
}
.pad-actions {
  padding: 12px 16px;
  border-top: 1px solid var(--line);
}
@media (max-width: 560px) {
  .form-grid-2 {
    grid-template-columns: 1fr;
  }
}
</style>
