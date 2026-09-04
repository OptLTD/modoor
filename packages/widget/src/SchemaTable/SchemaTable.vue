<template>
  <div class="table-wrap">
    <div class="toolbar">
      <div class="toolbar-left">
        <button
          v-for="c in createClicks"
          :key="c.uukey"
          type="button"
          class="btn primary"
          @click="onCreate"
        >
          {{ c.label || t('widget.create') }}
        </button>
        <button
          v-if="deleteEnabled"
          type="button"
          class="btn danger"
          :disabled="!selectedKeys.length"
          @click="onDelete"
        >
          {{
            selectedKeys.length
              ? t('widget.deleteSelected', { n: selectedKeys.length })
              : t('widget.delete')
          }}
        </button>
        <button
          v-if="activeFilterCount"
          type="button"
          class="btn"
          @click="clearAllFilters"
        >
          {{ t('widget.clearFilters', { n: activeFilterCount }) }}
        </button>
        <button type="button" class="btn" @click="exportAll">{{ t('widget.export') }}</button>
        <button
          type="button"
          class="btn"
          :disabled="!selectedKeys.length"
          @click="exportSelected"
        >
          {{ t('widget.exportSelected') }}
        </button>
      </div>
      <div class="toolbar-right">
        <span class="muted">{{ t('widget.totalRows', { n: count }) }}</span>
        <button type="button" class="btn" :disabled="page <= 1" @click="goto(page - 1)">{{ t('widget.prevPage') }}</button>
        <!-- <span class="page">{{ page }} / {{ pages }}</span> -->
        <button type="button" class="btn" :disabled="page >= pages" @click="goto(page + 1)">{{ t('widget.nextPage') }}</button>
        <button
          type="button"
          class="icon-btn"
          :class="{ active: panelFilterOpen }"
          :title="t('widget.filter')"
          @click="togglePanelFilter"
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path
              d="M2.5 3.5h11l-4 4.5V13l-3-1.5V8L2.5 3.5z"
              stroke="currentColor"
              stroke-width="1.4"
              stroke-linejoin="round"
            />
          </svg>
          <span v-if="activeFilterCount" class="icon-badge">{{ activeFilterCount }}</span>
        </button>
        <button
          :title="t('widget.refresh')"
          type="button"
          class="icon-btn"
          :disabled="loading"
          @click="reload"
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path
              d="M13.5 8a5.5 5.5 0 1 1-1.3-3.6"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
            />
            <path
              d="M13.5 3.2v3.1h-3.1"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
      </div>
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <div class="table-body">
      <div class="scroller" :class="{ loading }">
        <div class="list-frame" :class="{ 'has-totals': hasTotals }">
        <table class="list-grid">
          <thead>
            <tr>
              <th
                class="sticky-col sticky-check"
                :class="stickyEdgeOnCheck() ? 'sticky-edge' : ''"
                :style="{
                  left: '0px',
                  width: CHECK_W + 'px',
                  minWidth: CHECK_W + 'px',
                  maxWidth: CHECK_W + 'px',
                }"
              >
                <input
                  ref="checkAllRef"
                  type="checkbox"
                  :checked="allSelected"
                  @change="toggleAll"
                />
              </th>
            <th
              class="sticky-col sticky-action"
              :class="stickyEdgeOnAction() ? 'sticky-edge' : ''"
              :style="{
                left: CHECK_W + 'px',
                width: actionWidth + 'px',
                minWidth: actionWidth + 'px',
                maxWidth: actionWidth + 'px',
              }"
            >
              {{ t('widget.actions') }}
              <span
                class="col-resize"
                @mousedown.prevent.stop="startResize($event, ACTION_KEY, actionWidth, ACTION_MIN)"
              />
            </th>
            <th
              v-for="f in displayFields"
              :key="f.uukey"
              class="hdr-cell"
              :class="[
                isLastStickyField(f) ? 'sticky-edge' : '',
                isStickyField(f) ? 'sticky-col sticky-field' : '',
                isNumericCol(f) ? 'num' : '',
              ]"
              :style="{
                width: fieldWidth(f) + 'px',
                minWidth: fieldWidth(f) + 'px',
                maxWidth: fieldWidth(f) + 'px',
                left: isStickyField(f) ? stickyLeft(f) + 'px' : undefined,
              }"
            >
              <div class="hdr-inner">
                <span class="hdr-label truncate" :title="f.label || f.field">
                  {{ f.label || f.field }}
                </span>
                <div class="hdr-actions">
                  <button
                    :title="t('widget.filter')"
                    type="button"
                    class="hdr-icon"
                    :class="{
                      active: hasFilter(f),
                      open: filterOpen === fieldKey(f),
                    }"
                    @click.stop="openFilter(f)"
                  >
                    <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                      <path
                        d="M2.5 3.5h11l-4 4.5V13l-3-1.5V8L2.5 3.5z"
                        stroke="currentColor"
                        stroke-width="1.4"
                        stroke-linejoin="round"
                      />
                    </svg>
                  </button>
                  <button
                    v-if="isSortableField(f)"
                    type="button"
                    class="hdr-icon"
                    :class="sortState(f) ? 'active' : ''"
                    :title="
                      sortState(f) === 'asc'
                        ? t('widget.sortAsc')
                        : sortState(f) === 'desc'
                          ? t('widget.sortDesc')
                          : t('widget.sort')
                    "
                    @click.stop="toggleSort(f)"
                  >
                    <svg
                      v-if="sortState(f) === 'asc'"
                      width="12"
                      height="12"
                      viewBox="0 0 16 16"
                      fill="none"
                    >
                      <path
                        d="M8 3v10M8 3l3.5 3.5M8 3L4.5 6.5"
                        stroke="currentColor"
                        stroke-width="1.6"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                    </svg>
                    <svg
                      v-else-if="sortState(f) === 'desc'"
                      width="12"
                      height="12"
                      viewBox="0 0 16 16"
                      fill="none"
                    >
                      <path
                        d="M8 13V3M8 13l3.5-3.5M8 13L4.5 9.5"
                        stroke="currentColor"
                        stroke-width="1.6"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                    </svg>
                    <svg v-else width="12" height="12" viewBox="0 0 16 16" fill="none">
                      <path
                        d="M5 6l3-3 3 3M5 10l3 3 3-3"
                        stroke="currentColor"
                        stroke-width="1.4"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      />
                    </svg>
                  </button>
                </div>
              </div>
              <div
                v-if="filterOpen === fieldKey(f)"
                class="filter-pop"
                @click.stop
              >
                <label class="filter-label">
                  {{ t('widget.condition') }}
                  <select v-model="ensureDraft(f).op">
                    <option v-for="op in filterOps(f)" :key="op.value" :value="op.value">
                      {{ op.label }}
                    </option>
                  </select>
                </label>
                <template v-if="showValue(ensureDraft(f).op)">
                  <div
                    v-if="
                      (ftypeOf(f) === 'OPTIONAL' || ftypeOf(f) === 'RELATION') &&
                      hasReferOptions(f)
                    "
                    class="filter-input-wrap"
                  >
                    <SelectBox
                      :model-value="multiFilterValue(f)"
                      :options="optionsOf(f)"
                      :multiple="true"
                      :placeholder="t('widget.pleaseSelect')"
                      @update:model-value="(v) => onMultiFilterValue(f, v)"
                    />
                  </div>
                  <input
                    v-else-if="ftypeOf(f) === 'DATETIME'"
                    v-model="ensureDraft(f).value"
                    type="date"
                    class="filter-input"
                  />
                  <input
                    v-else-if="
                      ftypeOf(f) === 'NUMERIC' ||
                      ftypeOf(f) === 'EXPENSE' ||
                      ftypeOf(f) === 'INTEGER'
                    "
                    v-model="ensureDraft(f).value"
                    type="number"
                    class="filter-input"
                    :placeholder="t('widget.numberPh')"
                  />
                  <input
                    v-else
                    v-model="ensureDraft(f).value"
                    type="text"
                    class="filter-input"
                    :placeholder="t('widget.filterValue')"
                    @keydown.enter="applyFilter(f)"
                  />
                  <input
                    v-if="needsValue2(ensureDraft(f).op)"
                    v-model="ensureDraft(f).value2"
                    :type="ftypeOf(f) === 'DATETIME' ? 'date' : 'number'"
                    class="filter-input"
                    :placeholder="t('widget.endValue')"
                  />
                </template>
                <div class="filter-actions">
                  <button type="button" class="link" @click="clearFilter(f)">{{ t('widget.clear') }}</button>
                  <button type="button" class="link accent" @click="applyFilter(f)">{{ t('widget.apply') }}</button>
                </div>
              </div>
              <span
                class="col-resize"
                @mousedown.prevent.stop="startResize($event, f.field, fieldWidth(f))"
              />
            </th>
            <th class="list-fill" aria-hidden="true" />
          </tr>
        </thead>
        <tbody>
          <tr v-if="!loading && !rows.length">
            <td :colspan="displayFields.length + 3" class="empty">{{ t('widget.empty') }}</td>
          </tr>
          <tr
            v-for="(row, i) in rows"
            :key="rowKey(row) || i"
            class="data-row"
            @dblclick="onEdit(row)"
          >
            <td
              class="sticky-col sticky-check"
              :class="stickyEdgeOnCheck() ? 'sticky-edge' : ''"
              :style="{
                left: '0px',
                width: CHECK_W + 'px',
                minWidth: CHECK_W + 'px',
                maxWidth: CHECK_W + 'px',
              }"
            >
              <input
                type="checkbox"
                :checked="isRowSelected(row)"
                @click.stop
                @change="toggleOne(rowKey(row), $event)"
              />
            </td>
            <td
              class="sticky-col sticky-action"
              :class="stickyEdgeOnAction() ? 'sticky-edge' : ''"
              :style="{
                left: CHECK_W + 'px',
                width: actionWidth + 'px',
                minWidth: actionWidth + 'px',
                maxWidth: actionWidth + 'px',
              }"
            >
              <button type="button" class="link" @click="onEdit(row)">{{ t('widget.edit') }}</button>
            </td>
            <td
              v-for="f in displayFields"
              :key="f.uukey"
              class="truncate"
              :class="[
                isLastStickyField(f) ? 'sticky-edge' : '',
                isStickyField(f) ? 'sticky-col sticky-field' : '',
                isNumericCol(f) ? 'num' : '',
              ]"
              :style="{
                width: fieldWidth(f) + 'px',
                minWidth: fieldWidth(f) + 'px',
                maxWidth: fieldWidth(f) + 'px',
                left: isStickyField(f) ? stickyLeft(f) + 'px' : undefined,
              }"
              :title="String(displayCell(row, f))"
            >
              {{ displayCell(row, f) }}
            </td>
            <td class="list-fill" aria-hidden="true" />
          </tr>
        </tbody>
      </table>

        <div v-if="hasTotals" class="list-spacer" aria-hidden="true" />

        <table v-if="hasTotals" class="list-grid list-totals">
          <tbody>
            <tr>
              <td
                class="sticky-col sticky-check muted"
                :class="stickyEdgeOnCheck() ? 'sticky-edge' : ''"
                :style="{
                  left: '0px',
                  width: CHECK_W + 'px',
                  minWidth: CHECK_W + 'px',
                  maxWidth: CHECK_W + 'px',
                }"
              >
                {{ t('widget.sum') }}
              </td>
              <td
                class="sticky-col sticky-action"
                :class="stickyEdgeOnAction() ? 'sticky-edge' : ''"
                :style="{
                  left: CHECK_W + 'px',
                  width: actionWidth + 'px',
                  minWidth: actionWidth + 'px',
                  maxWidth: actionWidth + 'px',
                }"
              />
              <td
                v-for="f in displayFields"
                :key="'total-' + f.uukey"
                class="truncate"
                :class="[
                  isLastStickyField(f) ? 'sticky-edge' : '',
                  isStickyField(f) ? 'sticky-col sticky-field' : '',
                  isNumericCol(f) ? 'num' : '',
                ]"
                :style="{
                  width: fieldWidth(f) + 'px',
                  minWidth: fieldWidth(f) + 'px',
                  maxWidth: fieldWidth(f) + 'px',
                  left: isStickyField(f) ? stickyLeft(f) + 'px' : undefined,
                }"
                :title="formatTotalCell(f)"
              >
                {{ formatTotalCell(f) }}
              </td>
              <td class="list-fill" aria-hidden="true" />
            </tr>
          </tbody>
        </table>
        </div>
      <div v-if="loading" class="load-mask muted">{{ t('widget.loading') }}</div>
      </div>

      <aside v-if="panelFilterOpen" class="filter-drawer">
        <FilterPanel
          :fields="fields"
          :refers="theRefers"
          :model-value="appliedFilters"
          @update:model-value="onPanelFilters"
          @reset="clearAllFilters"
        />
      </aside>
    </div>

    <FormModal
      :open="formOpen"
      :model="table.model"
      :using="using"
      :fields="table.fields"
      :mode="formMode"
      :row="formRow"
      @close="closeForm"
      @saved="onFormSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { SchemaTable } from '@modoor/hooks'
import { useI18n } from '@modoor/hooks'
import { useSchemaTable } from './useSchemaTable'
import FilterPanel from '../FilterPanel/FilterPanel.vue'
import FormModal from '../FormModal/FormModal.vue'
import SelectBox from '../SelectBox/SelectBox.vue'

const props = defineProps<{
  table: SchemaTable
  using?: string
}>()

const { t } = useI18n()
const api = useSchemaTable(props)
const {
  CHECK_W,
  ACTION_MIN,
  ACTION_KEY,
  rows,
  count,
  page,
  pages,
  error,
  loading,
  selectedKeys,
  displayFields,
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
} = api

const checkAllRef = ref<HTMLInputElement | null>(null)
watch([allSelected, someSelected], () => {
  if (checkAllRef.value) checkAllRef.value.indeterminate = someSelected.value
})

defineExpose({ reload })
</script>

<style scoped>
.table-wrap {
  min-height: 0;
}
.table-body {
  display: flex;
  flex: 1;
  min-height: 0;
  align-items: stretch;
}
.filter-drawer {
  width: 280px;
  flex-shrink: 0;
  border-left: 1px solid var(--line);
  background: var(--panel);
  min-height: 0;
  align-self: stretch;
  overflow: hidden;
}
.icon-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: #fff;
  color: var(--muted);
  cursor: pointer;
}
.icon-btn:hover:not(:disabled) {
  color: var(--ink);
  background: #f8f4eb;
}
.icon-btn.active {
  color: var(--accent);
  border-color: color-mix(in srgb, var(--accent) 40%, var(--line));
  background: #eef6f3;
}
.icon-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.icon-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 14px;
  height: 14px;
  padding: 0 3px;
  background: var(--accent);
  color: #fff;
  font-size: 9px;
  line-height: 1;
}
.scroller {
  position: relative;
  overflow: auto;
  flex: 1;
  min-width: 0;
  min-height: 0;
}
.list-frame {
  display: flex;
  flex-direction: column;
  min-width: min-content;
}
.list-frame.has-totals {
  min-height: 100%;
}
.list-spacer {
  flex: 1 1 auto;
  min-height: 0;
}
.scroller.loading {
  min-height: 120px;
}
.load-mask {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, var(--panel) 72%, transparent);
  pointer-events: none;
}

.list-grid {
  border-collapse: separate;
  border-spacing: 0;
  table-layout: fixed;
  width: max-content;
  min-width: 100%;
  font-size: 0.92rem;
}
.list-grid th,
.list-grid td {
  border-bottom: 1px solid var(--line);
  border-right: 1px solid color-mix(in srgb, var(--line) 55%, transparent);
  padding: 8px 10px;
  text-align: left;
  background: var(--panel);
  white-space: nowrap;
  vertical-align: middle;
  overflow: hidden;
  box-sizing: border-box;
}
.list-grid thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: #f8f4eb;
  font-weight: 600;
}
.list-grid .hdr-cell,
.list-grid .sticky-action {
  /* sticky th 作为 col-resize 定位上下文 */
}
.list-grid .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.list-grid .empty {
  text-align: center;
  color: var(--muted);
  padding: 28px;
  border-right: none;
}
.list-grid .data-row:hover td {
  background: #f3f8f5;
}
.list-grid .data-row:hover .sticky-col {
  background: #f3f8f5;
}

.list-fill {
  width: auto;
  min-width: 0;
  padding: 0 !important;
  border-right: none !important;
  /* background: transparent !important; */
}

.list-totals {
  position: sticky;
  bottom: 0;
  z-index: 8;
  margin-top: -1px;
  flex-shrink: 0;
}
.list-totals td {
  background: #f8f4eb;
  color: var(--ink);
  border-bottom: none;
  box-shadow: 0 -1px 0 var(--line);
  font-weight: 600;
}

.sticky-col {
  position: sticky;
  background: var(--panel);
  z-index: 2;
}
thead .sticky-col {
  background: #f8f4eb;
  z-index: 4;
}
.list-totals .sticky-col {
  background: #f8f4eb;
  z-index: 9;
}
.sticky-check {
  z-index: 6;
  text-align: center;
}
thead .sticky-check,
.list-totals .sticky-check {
  z-index: 10;
  padding: 0px;
  text-align: center;
}
.sticky-action {
  z-index: 5;
  text-align: center;
}
thead .sticky-action,
.list-totals .sticky-action {
  z-index: 10;
}
.sticky-field {
  z-index: 3;
}
thead .sticky-field,
.list-totals .sticky-field {
  z-index: 9;
}
.sticky-edge {
  box-shadow: 2px 0 0 0 var(--line);
}

.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
}
.hdr-inner {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}
.hdr-label {
  flex: 1;
  min-width: 0;
}
.hdr-actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
}
.hdr-icon {
  display: none;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}
.hdr-cell:hover .hdr-icon {
  display: inline-flex;
}
.hdr-icon:hover {
  background: color-mix(in srgb, var(--line) 70%, #fff);
  color: var(--ink);
}
.hdr-icon.active,
.hdr-icon.open {
  display: inline-flex;
  color: var(--accent);
}

.col-resize {
  position: absolute;
  inset-y: 0;
  right: -3px;
  width: 8px;
  z-index: 6;
  cursor: col-resize;
  touch-action: none;
}
.col-resize:hover,
.col-resize:active {
  background: color-mix(in srgb, var(--accent) 28%, transparent);
}

.filter-pop {
  position: absolute;
  left: 0;
  top: 100%;
  z-index: 30;
  margin-top: 2px;
  width: 14rem;
  padding: 8px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  box-shadow: var(--shadow);
}
.filter-label {
  display: block;
  margin-bottom: 6px;
  font-size: 11px;
  color: var(--muted);
}
.filter-label select,
.filter-input {
  display: block;
  width: 100%;
  margin-top: 4px;
  margin-bottom: 6px;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 5px 8px;
  font: inherit;
  font-size: 12px;
  background: #fff;
}
.filter-input-wrap {
  margin-bottom: 6px;
}
.filter-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.link.accent {
  color: var(--accent);
  font-weight: 600;
}
</style>
