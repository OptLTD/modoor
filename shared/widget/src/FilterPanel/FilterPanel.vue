<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import type { SchemaField } from '@modoor/hooks'
import { referOptions, type ReferDict } from '@modoor/hooks'
import {
  defaultOp,
  filterOps,
  isDraftActive,
  needsValue2,
  showValue,
  type FilterDraft,
} from '@modoor/hooks'
import { fieldKey } from '@modoor/hooks'
import SelectBox, { type SelectOption } from '../SelectBox/SelectBox.vue'

const props = defineProps<{
  fields: SchemaField[]
  modelValue: Record<string, FilterDraft>
  refers?: ReferDict
}>()

const emit = defineEmits<{
  'update:modelValue': [Record<string, FilterDraft>]
  reset: []
}>()

const refers = computed(() => props.refers || {})

const filterFields = computed(() =>
  props.fields.filter(
    (f) => f.shown !== false && f.field && f.field !== 'model' && f.field !== 'state',
  ),
)

const draft = reactive<Record<string, FilterDraft>>({})

function ensure(f: SchemaField): FilterDraft {
  const fk = fieldKey(f)
  if (!draft[fk]) {
    const cur = props.modelValue[fk]
    draft[fk] = {
      op: cur?.op || defaultOp(f),
      value: cur?.value || '',
      value2: cur?.value2 || '',
    }
  }
  return draft[fk]
}

function syncDraft() {
  const present = new Set<string>()
  for (const f of filterFields.value) {
    const fk = fieldKey(f)
    present.add(fk)
    const cur = props.modelValue[fk]
    draft[fk] = {
      op: cur?.op || defaultOp(f),
      value: cur?.value || '',
      value2: cur?.value2 || '',
    }
  }
  for (const k of Object.keys(draft)) {
    if (!present.has(k)) delete draft[k]
  }
}
syncDraft()

watch(
  () => [props.fields.map((f) => f.uukey).join(','), JSON.stringify(props.modelValue || {})],
  syncDraft,
)

let timer: ReturnType<typeof setTimeout> | null = null
let lastJSON = ''

function scheduleEmit() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => {
    const out: Record<string, FilterDraft> = {}
    for (const f of filterFields.value) {
      const d = ensure(f)
      if (!d.op) continue
      out[fieldKey(f)] = { op: d.op, value: d.value, value2: d.value2 }
    }
    const json = JSON.stringify(out)
    if (json === lastJSON) return
    lastJSON = json
    emit('update:modelValue', out)
  }, 300)
}

watch(draft, scheduleEmit, { deep: true })

function autoSingleOp(f: SchemaField): string {
  if (isChoiceField(f)) return 'IN'
  const t = ftypeOf(f)
  if (t === 'NUMERIC' || t === 'EXPENSE' || t === 'INTEGER') return 'EQ'
  if (t === 'DATETIME') return 'EQ'
  return 'LIKE'
}

function autoAdjustOps() {
  for (const f of filterFields.value) {
    const d = draft[fieldKey(f)]
    if (!d) continue
    const op = d.op
    if (op === 'NIL' || op === 'NNL') continue
    const hasV = String(d.value ?? '').trim() !== ''
    const hasV2 = String(d.value2 ?? '').trim() !== ''
    if (op === 'BTW') {
      if (!hasV && !hasV2) d.op = 'ALL'
      continue
    }
    if (op === 'ALL') {
      if (ftypeOf(f) === 'DATETIME') {
        if (hasV && hasV2) d.op = 'BTW'
      } else if (hasV) {
        d.op = autoSingleOp(f)
      }
      continue
    }
    if (!hasV) d.op = 'ALL'
  }
}

watch(
  () =>
    filterFields.value
      .map((f) => {
        const d = draft[fieldKey(f)]
        return `${fieldKey(f)}:${d?.value ?? ''}|${d?.value2 ?? ''}`
      })
      .join('§'),
  autoAdjustOps,
)

function optionsOf(f: SchemaField) {
  return referOptions(f, refers.value)
}
function valueOptions(f: SchemaField): SelectOption[] {
  return optionsOf(f)
    .map((o) => ({
      label: String(o.label ?? o.value ?? ''),
      value: String(o.value ?? ''),
    }))
    .filter((o) => o.value !== '')
}
function ftypeOf(f: SchemaField) {
  return String(f.ftype || '').toUpperCase()
}
function hasOptions(f: SchemaField) {
  return optionsOf(f).length > 0
}
function isChoiceField(f: SchemaField): boolean {
  const t = ftypeOf(f)
  return (t === 'OPTIONAL' || t === 'RELATION') && hasOptions(f)
}

function multiValue(f: SchemaField): string[] {
  const v = ensure(f).value
  return String(v ?? '')
    .split(/[,\n]/)
    .map((s) => s.trim())
    .filter(Boolean)
}

function onMultiValue(f: SchemaField, v: string | string[]) {
  const arr = (Array.isArray(v) ? v : [v]).map((s) => String(s).trim()).filter(Boolean)
  const d = ensure(f)
  d.value = arr.join('\n')
  if (arr.length) d.op = 'IN'
  else if (d.op === 'IN') d.op = 'ALL'
}

function resetAll() {
  for (const f of filterFields.value) {
    draft[fieldKey(f)] = { op: defaultOp(f), value: '', value2: '' }
  }
  lastJSON = ''
  emit('reset')
  emit('update:modelValue', {})
}

const activeCount = computed(
  () => filterFields.value.filter((f) => isDraftActive(draft[fieldKey(f)])).length,
)
</script>

<template>
  <div class="filter-panel">
    <div class="panel-head">
      <div class="panel-title">
        筛选
        <span v-if="activeCount" class="badge">{{ activeCount }}</span>
      </div>
      <button
        type="button"
        class="link"
        :disabled="!activeCount"
        @click="resetAll"
      >
        重置
      </button>
    </div>

    <div class="panel-body">
      <div v-if="!filterFields.length" class="empty">暂无可筛选字段</div>
      <div v-for="f in filterFields" :key="f.uukey" class="filter-row">
        <div class="filter-head">
          <span
            class="field-name"
            :class="{ active: isDraftActive(draft[fieldKey(f)]) }"
            :title="f.label || f.field"
          >
            {{ f.label || f.field }}
          </span>
          <div class="op-select-wrap">
            <SelectBox
              v-model="ensure(f).op"
              :options="filterOps(f)"
              :clearable="false"
              placeholder=""
            />
          </div>
        </div>
        <div v-if="showValue(ensure(f).op)" class="filter-value">
          <div v-if="isChoiceField(f)" class="grow">
            <SelectBox
              :model-value="multiValue(f)"
              :options="valueOptions(f)"
              :multiple="true"
              placeholder="请选择"
              @update:model-value="(v) => onMultiValue(f, v)"
            />
          </div>
          <template v-else-if="ftypeOf(f) === 'DATETIME' && (ensure(f).op === 'BTW' || ensure(f).op === 'ALL')">
            <input v-model="ensure(f).value" type="date" class="filter-input grow" />
            <input v-model="ensure(f).value2" type="date" class="filter-input grow" />
          </template>
          <input
            v-else-if="ftypeOf(f) === 'DATETIME'"
            v-model="ensure(f).value"
            type="date"
            class="filter-input grow"
          />
          <input
            v-else-if="['NUMERIC', 'EXPENSE', 'INTEGER'].includes(ftypeOf(f))"
            v-model="ensure(f).value"
            type="number"
            class="filter-input grow"
            placeholder="数值"
          />
          <input
            v-else
            v-model="ensure(f).value"
            type="text"
            class="filter-input grow"
            placeholder="筛选值"
          />
          <input
            v-if="needsValue2(ensure(f).op) && ['NUMERIC', 'EXPENSE', 'INTEGER'].includes(ftypeOf(f))"
            v-model="ensure(f).value2"
            type="number"
            class="filter-input end"
            placeholder="结束"
          />
        </div>
      </div>
    </div>

    <div class="panel-foot muted">修改后自动应用</div>
  </div>
</template>

<style scoped>
.filter-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--line);
  flex-shrink: 0;
}
.panel-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.875rem;
  font-weight: 600;
}
.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  background: var(--accent);
  color: #fff;
  font-size: 10px;
  line-height: 1;
}
.panel-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 12px;
}
.empty {
  padding: 24px 0;
  text-align: center;
  font-size: 12px;
  color: var(--muted);
}
.filter-row {
  margin-bottom: 12px;
}
.filter-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.field-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 500;
  color: var(--muted);
}
.field-name.active {
  color: var(--accent);
}
.op-select-wrap {
  width: 88px;
  flex-shrink: 0;
}
.op-select-wrap :deep(.select-trigger) {
  min-height: 28px;
  padding: 0 6px;
  font-size: 11px;
  border-radius: 4px;
  background: #f8f4eb;
}
.filter-value {
  display: flex;
  align-items: center;
  gap: 6px;
}
.grow {
  flex: 1;
  min-width: 0;
}
.filter-input {
  height: 30px;
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: #fff;
  padding: 0 8px;
  font: inherit;
  font-size: 12px;
  color: var(--ink);
}
.filter-input.end {
  width: 5rem;
  flex-shrink: 0;
}
.panel-foot {
  flex-shrink: 0;
  padding: 8px 12px;
  border-top: 1px solid var(--line);
  font-size: 11px;
}
.panel-head .link:disabled {
  opacity: 0.4;
  cursor: default;
  text-decoration: none;
}
</style>
