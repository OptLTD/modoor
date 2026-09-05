import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import {
  deleteRecords,
  searchRecords,
  type SchemaClick,
  type SchemaField,
  type SchemaTable,
} from '@modoor/hooks'
import { exportRows } from '@modoor/hooks'
import {
  applyStickyOrder,
  displayFieldValue,
  isNumericField,
  isSortableField,
  mergeRefers,
  normalizeReferDict,
  referOptions,
  sortIndexField,
  type ReferDict,
} from '@modoor/hooks'
import {
  defaultOp,
  filterOps,
  isDraftActive,
  needsValue2,
  showValue,
  type FilterDraft,
} from '@modoor/hooks'
import {
  buildListQuery,
  fieldKey,
  mergeListQuery,
  rowUUKey,
  t,
} from '@modoor/hooks'

export const CHECK_W = 40
export const ACTION_MIN = 36
const ACTION_KEY = '__action__'

function widthStorageKey(model: string, id: string) {
  return `modoor.colWidth.${model}.${id}`
}

/**
 * Schema list：加载、列宽/sticky、筛选、排序、选择、表单、导出。
 */
export function useSchemaTable(props: {
  table: SchemaTable
  using?: string
  actionMin?: number
}) {
  const rows = ref<Record<string, unknown>[]>([])
  const totals = ref<Record<string, unknown>>({})
  const count = ref(0)
  const page = ref(1)
  const size = ref(50)
  const error = ref('')
  const loading = ref(false)
  const selectedKeys = ref<string[]>([])
  const order = ref<{ field: string; order: 'asc' | 'desc' } | null>(null)
  const theRefers = ref<ReferDict>({})

  const appliedFilters = reactive<Record<string, FilterDraft>>({})
  const filterDraft = reactive<Record<string, FilterDraft>>({})
  const filterOpen = ref<string | null>(null)
  const panelFilterOpen = ref(false)

  const formOpen = ref(false)
  const formMode = ref<'create' | 'edit'>('create')
  const formRow = ref<Record<string, unknown> | null>(null)

  const colWidths = reactive<Record<string, number>>({})
  const actionResizeMin = computed(() => Math.max(ACTION_MIN, props.actionMin ?? 48))
  const actionWidth = ref(actionResizeMin.value)

  const fields = computed(() => props.table.fields || [])
  const using = computed(() => props.using || props.table.using || 'default')

  const stickyKeys = computed(() => {
    const sticky = props.table.sticky
    const keys = sticky?.length ? [...sticky] : ['basic.uukey']
    return keys.filter((k) => fields.value.some((f) => f.uukey === k || `basic.${f.field}` === k))
  })

  const displayFields = computed(() => {
    const shown = fields.value.filter((f) => f.shown !== false && f.field)
    const keys = applyStickyOrder(
      shown.map((f) => f.uukey),
      stickyKeys.value,
    )
    const byKey = new Map(shown.map((f) => [f.uukey, f]))
    return keys.map((k) => byKey.get(k)).filter(Boolean) as SchemaField[]
  })

  const pages = computed(() => Math.max(1, Math.ceil(count.value / size.value)))
  const toolbarClicks = computed(() => props.table.clicks || [])
  const toolbarClusters = computed(() => {
    const out: { key: string; group?: string; clicks: SchemaClick[] }[] = []
    for (const c of toolbarClicks.value) {
      const g = String(c.group || '').trim() || undefined
      const last = out[out.length - 1]
      if (g && last?.group === g) {
        last.clicks.push(c)
        continue
      }
      out.push({ key: g ? `g:${g}` : c.uukey, group: g, clicks: [c] })
    }
    return out
  })
  const createClicks = computed(() =>
    toolbarClicks.value.filter(
      (c: SchemaClick) => c.action === 'record.create' || c.uukey === 'create',
    ),
  )
  const deleteEnabled = computed(() =>
    toolbarClicks.value.some((c) => c.action === 'record.delete' || c.uukey === 'delete'),
  )

  function fieldWidth(f: SchemaField) {
    if (colWidths[f.field]) return colWidths[f.field]
    return Math.max(80, Number(f.width) || 140)
  }

  function loadWidths() {
    const model = props.table.model
    for (const f of fields.value) {
      const raw = localStorage.getItem(widthStorageKey(model, f.field))
      if (raw) {
        const n = Number(raw)
        if (Number.isFinite(n) && n >= 60) colWidths[f.field] = n
      }
    }
    const aw = localStorage.getItem(widthStorageKey(model, ACTION_KEY))
    if (aw) {
      const n = Number(aw)
      if (Number.isFinite(n) && n >= actionResizeMin.value) actionWidth.value = n
      else actionWidth.value = actionResizeMin.value
    } else if (actionWidth.value < actionResizeMin.value) {
      actionWidth.value = actionResizeMin.value
    }
  }

  function isStickyField(f: SchemaField) {
    return stickyKeys.value.includes(f.uukey) || stickyKeys.value.includes(`basic.${f.field}`)
  }

  function stickyLeft(f: SchemaField) {
    let left = CHECK_W + actionWidth.value
    for (const sf of displayFields.value) {
      if (sf.field === f.field) break
      if (!isStickyField(sf)) break
      left += fieldWidth(sf)
    }
    return left
  }

  function isLastStickyField(f: SchemaField) {
    const stickyFs = displayFields.value.filter(isStickyField)
    return stickyFs.length > 0 && stickyFs[stickyFs.length - 1]?.field === f.field
  }

  function stickyEdgeOnAction() {
    return displayFields.value.filter(isStickyField).length === 0
  }

  function stickyEdgeOnCheck() {
    // 始终有操作列时，勾选列不画 sticky 边线
    return false
  }

  function startResize(e: MouseEvent, id: string, current: number, min = 60) {
    e.preventDefault()
    e.stopPropagation()
    const startX = e.clientX
    const startW = current
    const prevCursor = document.body.style.cursor
    const prevSelect = document.body.style.userSelect
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    const onMove = (ev: MouseEvent) => {
      const w = Math.max(min, startW + (ev.clientX - startX))
      if (id === ACTION_KEY) actionWidth.value = w
      else colWidths[id] = w
    }
    const onUp = () => {
      const w = id === ACTION_KEY ? actionWidth.value : colWidths[id] || startW
      localStorage.setItem(widthStorageKey(props.table.model, id), String(w))
      document.body.style.cursor = prevCursor
      document.body.style.userSelect = prevSelect
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  function rowKey(row: Record<string, unknown>) {
    return rowUUKey(row)
  }

  const allSelected = computed(
    () =>
      rows.value.length > 0 &&
      rows.value.every((r) => {
        const k = rowKey(r)
        return !!k && selectedKeys.value.includes(k)
      }),
  )
  const someSelected = computed(() => selectedKeys.value.length > 0 && !allSelected.value)

  function isRowSelected(row: Record<string, unknown>) {
    const key = rowKey(row)
    return !!key && selectedKeys.value.includes(key)
  }

  function displayCell(row: Record<string, unknown>, f: SchemaField) {
    return displayFieldValue(row, f, { refers: theRefers.value })
  }

  function totalValue(f: SchemaField): unknown {
    const t = totals.value || {}
    if (f.uukey in t) return t[f.uukey]
    if (f.field && f.field in t) return t[f.field]
    return undefined
  }

  function isNumericCol(f: SchemaField) {
    return isNumericField(f)
  }

  function formatTotalCell(f: SchemaField): string {
    const raw = totalValue(f)
    if (raw == null || raw === '') return ''
    const n = Number(raw)
    if (!Number.isFinite(n)) return String(raw)
    if (!isNumericCol(f)) {
      return new Intl.NumberFormat('zh-CN', { useGrouping: false }).format(n)
    }
    const precision = Number(f.extra?.precision ?? 0)
    const digits = Number.isFinite(precision) && precision >= 0 ? precision : 0
    return new Intl.NumberFormat('zh-CN', {
      useGrouping: false,
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(n)
  }

  const hasTotals = computed(() =>
    displayFields.value.some((f) => {
      const v = totalValue(f)
      return v != null && v !== ''
    }),
  )

  function optionsOf(f: SchemaField) {
    return referOptions(f, theRefers.value)
  }
  function hasReferOptions(f: SchemaField) {
    return optionsOf(f).length > 0
  }
  function ftypeOf(f: SchemaField) {
    return String(f.ftype || '').toUpperCase()
  }

  function buildQuery(): Record<string, unknown> | undefined {
    return mergeListQuery(
      buildListQuery(appliedFilters, fields.value),
      props.table.request?.query,
    )
  }

  async function reload() {
    loading.value = true
    error.value = ''
    try {
      const res = await searchRecords(props.table.model, using.value, page.value, size.value, {
        query: buildQuery(),
        order: order.value || undefined,
      })
      rows.value = res.values || []
      totals.value = (res.totals || {}) as Record<string, unknown>
      count.value = res.count ?? rows.value.length
      theRefers.value = mergeRefers(
        normalizeReferDict(props.table.refers as ReferDict),
        normalizeReferDict(res.refers),
      )
      selectedKeys.value = []
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      totals.value = {}
      count.value = 0
    } finally {
      loading.value = false
    }
  }

  function goto(p: number) {
    page.value = Math.min(Math.max(1, p), pages.value)
    void reload()
  }

  function toggleSort(f: SchemaField) {
    if (!isSortableField(f)) return
    const field = sortIndexField(f)
    if (!order.value || order.value.field !== field) {
      order.value = { field, order: 'asc' }
    } else if (order.value.order === 'asc') {
      order.value = { field, order: 'desc' }
    } else {
      order.value = null
    }
    page.value = 1
    void reload()
  }

  function sortState(f: SchemaField): 'asc' | 'desc' | '' {
    const field = sortIndexField(f)
    if (!isSortableField(f) || !order.value || order.value.field !== field) return ''
    return order.value.order === 'desc' ? 'desc' : 'asc'
  }

  function ensureDraft(f: SchemaField) {
    const fk = fieldKey(f)
    if (!filterDraft[fk]) {
      const applied = appliedFilters[fk]
      filterDraft[fk] = {
        op: applied?.op || defaultOp(f),
        value: applied?.value || '',
        value2: applied?.value2 || '',
      }
    }
    return filterDraft[fk]
  }

  function openFilter(f: SchemaField) {
    const fk = fieldKey(f)
    const applied = appliedFilters[fk]
    filterDraft[fk] = {
      op: applied?.op || defaultOp(f),
      value: applied?.value || '',
      value2: applied?.value2 || '',
    }
    filterOpen.value = filterOpen.value === fk ? null : fk
  }

  function hasFilter(f: SchemaField) {
    return isDraftActive(appliedFilters[fieldKey(f)])
  }

  function multiFilterValue(f: SchemaField): string[] {
    const v = ensureDraft(f).value
    return String(v ?? '')
      .split(/[,\n]/)
      .map((s) => s.trim())
      .filter(Boolean)
  }

  function onMultiFilterValue(f: SchemaField, v: string | string[]) {
    const arr = (Array.isArray(v) ? v : [v]).map((s) => String(s).trim()).filter(Boolean)
    const d = ensureDraft(f)
    d.value = arr.join('\n')
    if (arr.length) d.op = 'IN'
    else if (d.op === 'IN') d.op = 'ALL'
  }

  function applyFilter(f: SchemaField) {
    const d = ensureDraft(f)
    if (needsValue2(d.op) && (!d.value || !d.value2)) {
      error.value = t('widget.fillRange')
      return
    }
    if (d.op === 'ALL' && String(d.value ?? '').trim()) {
      d.op = hasReferOptions(f) ? 'IN' : 'LIKE'
    }
    const fk = fieldKey(f)
    if (!isDraftActive(d)) {
      delete appliedFilters[fk]
    } else {
      appliedFilters[fk] = { op: d.op, value: d.value, value2: d.value2 }
    }
    filterOpen.value = null
    page.value = 1
    void reload()
  }

  function clearFilter(f: SchemaField) {
    const fk = fieldKey(f)
    delete appliedFilters[fk]
    filterDraft[fk] = { op: defaultOp(f), value: '', value2: '' }
    filterOpen.value = null
    page.value = 1
    void reload()
  }

  function clearAllFilters() {
    for (const k of Object.keys(appliedFilters)) delete appliedFilters[k]
    for (const k of Object.keys(filterDraft)) delete filterDraft[k]
    filterOpen.value = null
    page.value = 1
    void reload()
  }

  function onPanelFilters(next: Record<string, FilterDraft>) {
    for (const k of Object.keys(appliedFilters)) delete appliedFilters[k]
    for (const [k, v] of Object.entries(next || {})) {
      if (v) appliedFilters[k] = { op: v.op, value: v.value, value2: v.value2 }
    }
    page.value = 1
    void reload()
  }

  function togglePanelFilter() {
    panelFilterOpen.value = !panelFilterOpen.value
  }

  const activeFilterCount = computed(
    () => Object.values(appliedFilters).filter((d) => isDraftActive(d)).length,
  )

  function toggleAll(e?: Event) {
    const el = e?.target as HTMLInputElement | undefined
    const checked = el && typeof el.checked === 'boolean' ? el.checked : !allSelected.value
    selectedKeys.value = checked ? rows.value.map(rowKey).filter((k) => !!k) : []
  }

  function toggleOne(key: string, e?: Event) {
    const k = String(key || '').trim()
    if (!k) return
    const el = e?.target as HTMLInputElement | undefined
    const checked =
      el && typeof el.checked === 'boolean' ? el.checked : !selectedKeys.value.includes(k)
    if (checked) {
      if (!selectedKeys.value.includes(k)) selectedKeys.value = [...selectedKeys.value, k]
    } else {
      selectedKeys.value = selectedKeys.value.filter((x) => x !== k)
    }
  }

  function getSelectedRows() {
    const set = new Set(selectedKeys.value)
    return rows.value.filter((r) => set.has(rowKey(r)))
  }

  function onCreate() {
    formMode.value = 'create'
    const defaults = (props.table as SchemaTable & { createDefaults?: Record<string, unknown> })
      .createDefaults
    formRow.value = defaults && Object.keys(defaults).length ? { ...defaults } : null
    formOpen.value = true
  }

  function onEdit(row: Record<string, unknown>) {
    formMode.value = 'edit'
    formRow.value = row
    formOpen.value = true
  }

  function closeForm() {
    formOpen.value = false
  }

  async function onFormSaved() {
    formOpen.value = false
    await reload()
  }

  async function onDelete() {
    const keys = [...selectedKeys.value].map(String).filter((k) => k.trim())
    if (!keys.length) {
      error.value = t('widget.pickDeleteRows')
      return
    }
    if (!confirm(t('widget.confirmDeleteRows', { n: keys.length }))) return
    error.value = ''
    try {
      await deleteRecords(props.table.model, keys)
      selectedKeys.value = []
      await reload()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    }
  }

  async function exportAll() {
    try {
      const pageSize = 100
      const max = 500
      const all: Record<string, unknown>[] = []
      let pageNo = 1
      let total = Infinity
      const q = buildQuery()
      while (all.length < max && all.length < total) {
        const res = await searchRecords(props.table.model, using.value, pageNo, pageSize, {
          query: q,
          order: order.value || undefined,
        })
        total = res.count ?? 0
        const batch = res.values || []
        if (!batch.length) break
        all.push(...batch)
        Object.assign(theRefers.value, normalizeReferDict(res.refers))
        if (batch.length < pageSize) break
        pageNo += 1
      }
      if (!all.length) {
        error.value = t('widget.noExportData')
        return
      }
      if (total > max && !confirm(t('widget.exportTruncated', { total, max }))) return
      await exportRows({
        title: props.table.title?.trim() || props.table.model,
        fields: fields.value,
        rows: all.slice(0, max),
        refers: theRefers.value,
      })
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    }
  }

  async function exportSelected() {
    const selected = getSelectedRows()
    if (!selected.length) {
      error.value = t('widget.pickExportRows')
      return
    }
    try {
      await exportRows({
        title: props.table.title?.trim() || props.table.model,
        fields: fields.value,
        rows: selected,
        refers: theRefers.value,
      })
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    }
  }

  function onDocClick(ev: MouseEvent) {
    if (!filterOpen.value) return
    const t = ev.target as HTMLElement | null
    if (t?.closest?.('.filter-pop') || t?.closest?.('.hdr-icon') || t?.closest?.('.select-panel')) {
      return
    }
    filterOpen.value = null
  }

  watch(actionResizeMin, (min) => {
    if (actionWidth.value < min) actionWidth.value = min
  })

  watch(
    () => props.table.model,
    () => {
      page.value = 1
      order.value = null
      for (const k of Object.keys(appliedFilters)) delete appliedFilters[k]
      loadWidths()
      void reload()
    },
  )

  onMounted(() => {
    loadWidths()
    const req = props.table.request
    if (req?.page) page.value = req.page
    if (req?.size) size.value = req.size
    if (req?.order?.field) {
      order.value = {
        field: req.order.field,
        order: req.order.order === 'asc' ? 'asc' : 'desc',
      }
    }
    document.addEventListener('click', onDocClick)
    void reload()
  })

  onUnmounted(() => {
    document.removeEventListener('click', onDocClick)
  })

  return {
    CHECK_W,
    ACTION_MIN,
    actionResizeMin,
    ACTION_KEY,
    rows,
    totals,
    count,
    page,
    size,
    pages,
    error,
    loading,
    selectedKeys,
    displayFields,
    toolbarClusters,
    createClicks,
    deleteEnabled,
    actionWidth,
    allSelected,
    someSelected,
    hasTotals,
    filterOpen,
    panelFilterOpen,
    appliedFilters,
    theRefers,
    fields,
    activeFilterCount,
    formOpen,
    formMode,
    formRow,
    using,
    fieldKey,
    fieldWidth,
    isStickyField,
    stickyLeft,
    isLastStickyField,
    stickyEdgeOnAction,
    stickyEdgeOnCheck,
    startResize,
    rowKey,
    isRowSelected,
    displayCell,
    formatTotalCell,
    isNumericCol,
    isSortableField,
    sortState,
    toggleSort,
    goto,
    reload,
    toggleAll,
    toggleOne,
    onCreate,
    onEdit,
    onDelete,
    closeForm,
    onFormSaved,
    exportAll,
    exportSelected,
    optionsOf,
    hasReferOptions,
    ftypeOf,
    filterOps,
    showValue,
    needsValue2,
    ensureDraft,
    openFilter,
    hasFilter,
    multiFilterValue,
    onMultiFilterValue,
    applyFilter,
    clearFilter,
    clearAllFilters,
    onPanelFilters,
    togglePanelFilter,
  }
}
