<template>
  <section
    class="folder-layout"
    :class="{ 'drag-over': dragOver }"
    @dragenter.prevent="onDragEnter"
    @dragover.prevent="onDragOver"
    @dragleave.prevent="onDragLeave"
    @drop.prevent="onDrop"
  >
    <div v-if="dragOver" class="drop-overlay" aria-hidden="true">
      <p>{{ t('doc.dropToUpload') }}</p>
    </div>
    <aside class="sidebar">
      <div class="side-head">
        <div class="side-title">
          <h1>{{ t('doc.library') }}</h1>
        </div>
        <div class="view-modes" role="group" aria-label="view">
          <button
            type="button"
            class="mode-btn"
            :class="{ 
              active: viewMode === 'list' 
            }"
            @click="viewMode = 'list'"
          >
            {{ t('doc.viewList') }}
          </button>
          <button
            type="button"
            class="mode-btn"
            :class="{ active: viewMode === 'icon' }"
            @click="viewMode = 'icon'"
          >
            {{ t('doc.viewIcon') }}
          </button>
          <button
            type="button"
            class="mode-btn"
            :class="{ active: viewMode === 'split' }"
            @click="viewMode = 'split'"
          >
            {{ t('doc.viewSplit') }}
          </button>
        </div>
      </div>

      <label class="btn primary upload-btn" :class="{ busy: uploading }">
        {{ uploading ? t('doc.uploading') : t('doc.upload') }}
        <input
          type="file"
          hidden
          multiple
          :disabled="uploading"
          @change="onUpload"
        />
      </label>

      <nav class="tag-nav">
        <button
          type="button"
          class="tag-item"
          :class="{ active: !activeTag }"
          @click="selectTag('')"
        >
          {{ t('common.all') }}
        </button>
        <button
          v-for="t in tags"
          :key="t.tag"
          type="button"
          class="tag-item"
          :class="{ active: activeTag === t.tag }"
          @click="selectTag(t.tag)"
        >
          <span>{{ t.tag }}</span>
          <span class="muted">{{ t.count }}</span>
        </button>
      </nav>

      <p v-if="error" class="error side-error">{{ error }}</p>
    </aside>

    <main class="content">
      <!-- list -->
      <div v-if="viewMode === 'list'" class="view-body">
        <table class="file-table">
          <thead>
            <tr>
              <th>{{ t('doc.colName') }}</th>
              <th>{{ t('doc.colType') }}</th>
              <th>{{ t('doc.colSize') }}</th>
              <th>{{ t('doc.colUpdated') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="a in items"
              :key="a.id"
              class="file-row"
              @click="openFile(a.id)"
              @dblclick="openFile(a.id)"
            >
              <td>
                <span class="type-badge">{{ typeLabel(a) }}</span>
                <span class="file-title">{{ a.title }}</span>
                <span class="muted file-sub">{{ a.filename }}</span>
              </td>
              <td class="muted mono">{{ extOf(a) || '—' }}</td>
              <td class="muted">{{ formatSize(a.size_bytes) }}</td>
              <td class="muted">{{ formatTime(a.updated_at) }}</td>
            </tr>
            <tr v-if="!items.length">
              <td colspan="4" class="empty muted">{{ t('doc.empty') }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- icon -->
      <div v-else-if="viewMode === 'icon'" class="view-body icon-grid">
        <button
          v-for="a in items"
          :key="a.id"
          type="button"
          class="icon-tile"
          @click="openFile(a.id)"
        >
          <span class="icon-glyph">{{ typeLabel(a) }}</span>
          <span class="icon-title">{{ a.title }}</span>
          <span class="muted icon-sub">{{ extOf(a) || 'file' }} · {{ formatSize(a.size_bytes) }}</span>
        </button>
        <p v-if="!items.length" class="empty muted">{{ t('doc.empty') }}</p>
      </div>

      <!-- split -->
      <div v-else class="view-body split-view">
        <ul class="split-list">
          <li
            v-for="a in items"
            :key="a.id"
            class="split-item"
            :class="{ active: focusId === a.id }"
            @click="focusId = a.id"
            @dblclick="openFile(a.id)"
          >
            <strong>{{ a.title }}</strong>
            <span class="muted">{{ typeLabel(a) }} · {{ formatSize(a.size_bytes) }}</span>
          </li>
          <li v-if="!items.length" class="muted empty">{{ t('doc.empty') }}</li>
        </ul>
        <div class="split-preview">
          <div v-if="focusAsset" class="split-preview-head">
            <div>
              <strong>{{ focusAsset.title }}</strong>
              <p class="muted">{{ focusAsset.filename }}</p>
            </div>
            <button type="button" class="btn" @click="openFile(focusAsset.id)">{{ t('doc.open') }}</button>
          </div>
          <PreviewPane v-if="focusAsset" :asset="focusAsset" />
          <p v-else class="empty muted">{{ t('doc.pickPreview') }}</p>
        </div>
      </div>
    </main>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { registerShellSearch, useI18n } from '@modoor/hooks'
import {
  getAsset,
  listAssets,
  listTags,
  uploadAsset,
  type DocAsset,
  type TagItem,
} from '../api/doc'
import PreviewPane from '../components/PreviewPane.vue'

type ViewMode = 'list' | 'icon' | 'split'

const VIEW_KEY = 'doc.folder.view'

const router = useRouter()
const { t } = useI18n()
const error = ref('')
const items = ref<DocAsset[]>([])
const tags = ref<TagItem[]>([])
const q = ref('')
const activeTag = ref('')
const uploading = ref(false)
const focusId = ref<string | null>(null)
const focusAsset = ref<DocAsset | null>(null)
const dragOver = ref(false)
let dragDepth = 0

const viewMode = ref<ViewMode>((() => {
  try {
    const v = localStorage.getItem(VIEW_KEY)
    if (v === 'list' || v === 'icon' || v === 'split') return v
  } catch {
    /* ignore */
  }
  return 'list'
})())

watch(viewMode, (v) => {
  try {
    localStorage.setItem(VIEW_KEY, v)
  } catch {
    /* ignore */
  }
  if (v === 'split' && !focusId.value && items.value[0]) {
    focusId.value = items.value[0].id
  }
})

const focusStillExists = computed(() =>
  focusId.value ? items.value.some((a) => a.id === focusId.value) : false,
)

function formatSize(n: number) {
  if (!n) return '0 B'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

function formatTime(raw?: string | null) {
  if (!raw) return '—'
  try {
    return new Date(raw).toLocaleString()
  } catch {
    return raw
  }
}

function extOf(a: DocAsset) {
  return (a.ext || a.filename.split('.').pop() || '').toLowerCase()
}

function typeLabel(a: DocAsset) {
  const e = extOf(a)
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(e)) return t('doc.typeImage')
  if (e === 'pdf') return t('doc.typePdf')
  if (['txt', 'md', 'csv', 'json', 'log'].includes(e)) return t('doc.typeText')
  if (e === 'xlsx' || e === 'xls') return t('doc.typeExcel')
  if (e === 'docx' || e === 'doc') return t('doc.typeWord')
  if (e === 'pptx' || e === 'ppt') return t('doc.typePpt')
  return e ? e.toUpperCase() : t('doc.typeFile')
}

function openFile(id: string) {
  void router.push(`/web/doc/${encodeURIComponent(id)}`)
}

async function reload() {
  error.value = ''
  try {
    const [assetsRes, tagsRes] = await Promise.all([
      listAssets({
        q: q.value.trim() || undefined,
        tag: activeTag.value || undefined,
        limit: 200,
      }),
      listTags(),
    ])
    items.value = assetsRes.items || []
    tags.value = tagsRes.items || []
    if (focusId.value && !focusStillExists.value) {
      focusId.value = items.value[0]?.id ?? null
    } else if (viewMode.value === 'split' && !focusId.value && items.value[0]) {
      focusId.value = items.value[0].id
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

async function loadFocus() {
  if (!focusId.value || viewMode.value !== 'split') {
    focusAsset.value = null
    return
  }
  try {
    const res = await getAsset(focusId.value)
    focusAsset.value = res.asset
  } catch (e) {
    focusAsset.value = null
    error.value = e instanceof Error ? e.message : String(e)
  }
}

function selectTag(tag: string) {
  activeTag.value = tag
  void reload()
}

async function uploadFiles(files: File[]) {
  const list = files.filter(Boolean)
  if (!list.length) return
  uploading.value = true
  error.value = ''
  try {
    const tagHint = activeTag.value ? [activeTag.value] : undefined
    let lastId = ''
    for (const file of list) {
      const res = await uploadAsset(file, { tags: tagHint })
      lastId = res.asset.id
    }
    await reload()
    if (lastId) await router.push(`/web/doc/${encodeURIComponent(lastId)}`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    uploading.value = false
  }
}

async function onUpload(ev: Event) {
  const input = ev.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  await uploadFiles(files)
}

function onDragEnter(ev: DragEvent) {
  if (!ev.dataTransfer?.types.includes('Files')) return
  dragDepth += 1
  dragOver.value = true
}

function onDragOver(ev: DragEvent) {
  if (!ev.dataTransfer?.types.includes('Files')) return
  ev.dataTransfer.dropEffect = 'copy'
  dragOver.value = true
}

function onDragLeave() {
  dragDepth = Math.max(0, dragDepth - 1)
  if (dragDepth === 0) dragOver.value = false
}

async function onDrop(ev: DragEvent) {
  dragDepth = 0
  dragOver.value = false
  const files = Array.from(ev.dataTransfer?.files || [])
  await uploadFiles(files)
}

watch(focusId, () => {
  void loadFocus()
})
watch(viewMode, () => {
  void loadFocus()
})

let unregisterSearch: (() => void) | null = null

onMounted(() => {
  void reload()
  unregisterSearch = registerShellSearch('doc.folder', (query) => {
    q.value = query
    void reload()
  })
})

onUnmounted(() => {
  unregisterSearch?.()
  unregisterSearch = null
})
</script>

<style scoped>
.folder-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(200px, 260px) 1fr;
  gap: 0;
  overflow: hidden;
  margin: -16px -16px;
  position: relative;
}

.folder-layout.drag-over {
  outline: 2px dashed var(--accent, #2563eb);
  outline-offset: -6px;
}

.drop-overlay {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, var(--accent, #2563eb) 12%, transparent);
  pointer-events: none;
}

.drop-overlay p {
  margin: 0;
  padding: 0.75rem 1.25rem;
  border-radius: 8px;
  background: var(--panel, #fff);
  border: 1px solid var(--line, #ddd);
  font-weight: 600;
}

.sidebar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 8px 14px 14px 8px;
  border-right: 1px solid var(--line);
  min-height: 0;
  overflow: auto;
}

.side-head {
  gap: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.side-title {
  min-width: 0;
}

.side-title h1 {
  margin: 0;
  font-size: 1.05rem;
}

.side-title .muted {
  margin: 4px 0 0;
  font-size: 0.8rem;
}

.upload-btn {
  cursor: pointer;
  text-align: center;
  width: 100%;
}

.upload-btn.busy {
  opacity: 0.7;
  cursor: wait;
}

.view-modes {
  display: inline-flex;
  border: 1px solid var(--line);
  border-radius: 6px;
  overflow: hidden;
  flex-shrink: 0;
}

.mode-btn {
  border: 0;
  background: transparent;
  padding: 5px 8px;
  font: inherit;
  font-size: 0.78rem;
  cursor: pointer;
  color: var(--muted);
  white-space: nowrap;
}

.mode-btn + .mode-btn {
  border-left: 1px solid var(--line);
}

.mode-btn.active {
  background: #eef6f3;
  color: var(--accent);
  font-weight: 600;
}

.tag-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 4px;
}

.tag-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  border: 0;
  background: transparent;
  text-align: left;
  padding: 7px 8px;
  border-radius: 6px;
  font: inherit;
  cursor: pointer;
  color: inherit;
}

.tag-item:hover {
  background: #f8f4eb;
}

.tag-item.active {
  background: #eef6f3;
  color: var(--accent);
  font-weight: 600;
}

.side-error {
  margin: 0;
  font-size: 0.82rem;
}

.content {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
}

.view-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.file-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
}

.file-table th {
  text-align: left;
  font-size: 0.75rem;
  color: var(--muted);
  font-weight: 600;
  border-bottom: 1px solid var(--line);
  padding: 8px 12px;
  position: sticky;
  top: 0;
  background: var(--bg, #f3efe6);
}

.file-row {
  cursor: pointer;
}

.file-row:hover {
  background: #f8f4eb;
}

.file-row td {
  padding: 9px 12px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 65%, transparent);
  vertical-align: middle;
}

.type-badge {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
  background: #0000000a;
  margin-right: 8px;
}

.file-title {
  font-weight: 600;
}

.file-sub {
  margin-left: 8px;
  font-size: 0.78rem;
}

.mono {
  text-transform: uppercase;
  font-size: 0.78rem;
}

.icon-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
  align-content: start;
  padding: 12px;
}

.icon-tile {
  display: grid;
  justify-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  padding: 12px 8px;
  border-radius: 8px;
  cursor: pointer;
  font: inherit;
  color: inherit;
  text-align: center;
}

.icon-tile:hover {
  background: #f8f4eb;
}

.icon-glyph {
  display: grid;
  place-items: center;
  width: 56px;
  height: 64px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.icon-title {
  font-size: 0.85rem;
  font-weight: 600;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.icon-sub {
  font-size: 0.72rem;
}

.split-view {
  display: grid;
  grid-template-columns: minmax(200px, 280px) 1fr;
  gap: 0;
  overflow: hidden;
}

.split-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow: auto;
  border-right: 1px solid var(--line);
}

.split-item {
  display: grid;
  gap: 2px;
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 60%, transparent);
}

.split-item:hover {
  background: #f8f4eb;
}

.split-item.active {
  background: #eef6f3;
}

.split-item strong {
  font-size: 0.92rem;
}

.split-item .muted {
  font-size: 0.78rem;
}

.split-preview {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
}

.split-preview-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
  flex-shrink: 0;
}

.split-preview-head .muted {
  margin: 2px 0 0;
  font-size: 0.8rem;
}

.split-preview :deep(.preview-pane) {
  flex: 1;
  min-height: 0;
  padding: 12px;
}

.empty {
  padding: 28px 8px;
  text-align: center;
}

@media (max-width: 860px) {
  .folder-layout {
    grid-template-columns: 1fr;
  }
  .sidebar {
    border-right: 0;
    border-bottom: 1px solid var(--line);
    max-height: 280px;
  }
  .split-view {
    grid-template-columns: 1fr;
  }
  .split-list {
    max-height: 180px;
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
}
</style>
