<template>
  <section class="workspace">
    <div class="ws-head">
      <div class="ws-title-row">
        <h1>{{ title }}{{ viewModeLabel }}</h1>
        <div v-if="viewMode !== 'table'" class="ws-sheet-actions">
          <button
            v-if="viewMode === 'import'"
            type="button"
            class="btn"
            :disabled="sheetBusy"
            @click="sheetRef?.addRows?.(10)"
          >
            {{ t('sale.addRows') }}
          </button>
          <button
            type="button"
            class="btn primary"
            :disabled="sheetBusy"
            @click="onSheetSave"
          >
            {{ sheetBusy ? t('sale.saving') : t('sale.save') }}
          </button>
          <button type="button" class="btn" @click="exitSheet">{{ t('sale.backList') }}</button>
        </div>
        <div v-else class="ws-sheet-actions">
          <button type="button" class="btn" @click="enterSheet('edit')">{{ t('sale.batchEdit') }}</button>
          <button type="button" class="btn" @click="enterSheet('import')">{{ t('sale.batchImport') }}</button>
        </div>
      </div>
    </div>

    <p v-if="bootError" class="error">{{ bootError }}</p>
    <p v-if="sheetError" class="error">{{ sheetError }}</p>
    <p v-if="sheetMessage" class="muted pad-msg">{{ sheetMessage }}</p>

    <SchemaTable
      v-if="table && viewMode === 'table'"
      ref="tableRef"
      :table="table"
      :using="using"
    />

    <SchemaSheet
      v-else-if="table && (viewMode === 'edit' || viewMode === 'import')"
      ref="sheetRef"
      class="sheet-pane"
      :table="sheetTable"
      :request="sheetRequest"
      :mode="viewMode"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref, watch } from 'vue'
import {
  fetchSchema,
  useI18n,
  type SchemaRequest,
  type SchemaTable as SchemaTableData,
} from '@modoor/hooks'
import { SchemaTable } from '@modoor/widget/SchemaTable'

const { t } = useI18n()

/** jspreadsheet 很重：仅在进入批量编辑/导入时再加载 */
const SchemaSheet = defineAsyncComponent(() =>
  import('@modoor/widget/SchemaSheet').then((m) => m.SchemaSheet),
)

const props = defineProps<{ model: string }>()

const using = ref('default')
const table = ref<SchemaTableData | null>(null)
const title = ref('')
const bootError = ref('')
const tableRef = ref<{ reload: () => Promise<void> } | null>(null)
const sheetRef = ref<{
  reload: () => Promise<void>
  addRows?: (n?: number) => Promise<void>
  saveAll: () => Promise<void>
  saving: boolean
  error: string
  message: string
} | null>(null)

type ViewMode = 'table' | 'edit' | 'import'
const viewMode = ref<ViewMode>('table')

const viewModeLabel = computed(() => {
  if (viewMode.value === 'edit') return t('sale.batchEditSuffix')
  if (viewMode.value === 'import') return t('sale.batchImportSuffix')
  return ''
})

const sheetTable = computed((): SchemaTableData => {
  const t = table.value!
  return {
    model: t.model,
    using: t.using || using.value,
    title: t.title,
    fields: t.fields,
    sticky: t.sticky,
    refers: t.refers,
  }
})

const sheetRequest = computed((): SchemaRequest => ({
  page: 1,
  size: viewMode.value === 'edit' ? 200 : 50,
  query: table.value?.request?.query,
}))

const sheetBusy = computed(() => !!sheetRef.value?.saving)
const sheetError = computed(() => sheetRef.value?.error || '')
const sheetMessage = computed(() => sheetRef.value?.message || '')

async function boot() {
  bootError.value = ''
  viewMode.value = 'table'
  try {
    const res = await fetchSchema(props.model, using.value)
    table.value = { ...res.table, model: res.model, using: res.using }
    title.value = res.table.title || res.model
  } catch (e) {
    bootError.value = e instanceof Error ? e.message : String(e)
  }
}

function enterSheet(mode: 'edit' | 'import') {
  viewMode.value = mode
}

async function exitSheet() {
  viewMode.value = 'table'
  await tableRef.value?.reload()
}

async function onSheetSave() {
  await sheetRef.value?.saveAll()
}

watch(
  () => props.model,
  () => boot(),
)

onMounted(boot)
</script>

<style scoped>
.ws-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.ws-sheet-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.pad-msg {
  padding: 0 16px 8px;
  font-size: 0.85rem;
}
.sheet-pane {
  flex: 1;
  min-height: 0;
}
</style>
