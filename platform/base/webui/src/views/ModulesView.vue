<template>
  <section class="panel modules-page">
    <header class="modules-head">
      <div>
        <h1>{{ t('base.modules') }}</h1>
        <p class="muted">{{ t('base.modulesIntro') }}</p>
      </div>
      <input
        v-model="keyword"
        class="modules-search"
        type="search"
        :placeholder="t('base.modulesSearchPh')"
      />
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="allTags.length" class="tag-bar">
      <button
        type="button"
        class="tag-chip"
        :class="{ active: !activeTags.length }"
        @click="activeTags = []"
      >
        {{ t('common.all') }}
      </button>
      <button
        v-for="tag in allTags"
        :key="tag"
        type="button"
        class="tag-chip"
        :class="{ active: activeTags.includes(tag) }"
        @click="toggleTag(tag)"
      >
        {{ tag }}
      </button>
    </div>

    <p v-if="!filtered.length && !error" class="muted empty-hint">{{ t('base.modulesEmpty') }}</p>

    <div class="module-grid">
      <article
        v-for="m in filtered"
        :key="m.id"
        class="module-card"
        :class="{ off: !m.enabled }"
      >
        <div class="card-top">
          <div class="card-title">
            <h2>{{ m.label || m.id }}</h2>
          </div>
          <span class="state-pill" :class="m.enabled ? 'on' : 'off'">
            {{ m.enabled ? 'enabled' : 'disabled' }}
          </span>
        </div>

        <p class="summary">{{ m.summary || '—' }}</p>

    
        <div v-if="displayTags(m).length" class="card-tags">
          <button
            v-for="tag in displayTags(m)"
            :key="tag"
            type="button"
            class="mini-tag"
            @click="toggleTag(tag)"
          >
            {{ tag }}
          </button>
        </div>

        <div class="card-foot">
          <div class="meta-row">
            <!-- <span v-if="m.kind" class="meta">{{ m.kind }}</span> -->
            <span v-if="m.version" class="meta">v{{ m.version }}</span>
            <span v-if="m.always_on" class="meta lock">always on</span>
          </div>

          <button
            v-if="!m.always_on"
            class="btn"
            type="button"
            @click="onToggle(m.id, !m.enabled)"
          >
            {{ m.enabled ? t('base.disable') : t('base.enable') }}
          </button>
          <span v-else class="muted">{{ t('base.coreModule') }}</span>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from '@modoor/hooks'
import { listModules, toggleModule, type ModuleItem } from '../api/base'

const { t } = useI18n()
const error = ref('')
const keyword = ref('')
const modules = ref<ModuleItem[]>([])
const activeTags = ref<string[]>([])

const allTags = computed(() => {
  const set = new Set<string>()
  for (const m of modules.value) {
    for (const t of m.tags || []) set.add(t)
  }
  return [...set].sort((a, b) => a.localeCompare(b, 'zh-CN'))
})

const filtered = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  const tags = activeTags.value
  return modules.value.filter((m) => {
    if (tags.length) {
      const mt = new Set(m.tags || [])
      if (!tags.every((t) => mt.has(t))) return false
    }
    if (!q) return true
    const hay = [
      m.id,
      m.label,
      m.summary,
      m.kind,
      m.version,
      ...(m.tags || []),
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return hay.includes(q)
  })
})

function displayTags(m: ModuleItem) {
  return (m.tags || []).filter((t) => t !== 'enabled' && t !== 'disabled')
}

function toggleTag(tag: string) {
  if (activeTags.value.includes(tag)) {
    activeTags.value = activeTags.value.filter((t) => t !== tag)
  } else {
    activeTags.value = [...activeTags.value, tag]
  }
}

async function reload() {
  error.value = ''
  try {
    const res = await listModules()
    modules.value = res.modules || []
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

async function onToggle(id: string, enabled: boolean) {
  try {
    await toggleModule(id, enabled)
    await reload()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

onMounted(reload)
</script>

<style scoped>
.modules-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
}

.modules-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}

.modules-head h1 {
  margin-bottom: 4px;
}

.modules-head .muted {
  margin: 0;
  max-width: 36rem;
}

.modules-search {
  width: min(280px, 100%);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 8px 10px;
  font: inherit;
  background: #fff;
}

.tag-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-chip {
  border: 1px solid var(--line);
  background: #fff;
  color: var(--muted);
  border-radius: 999px;
  padding: 4px 10px;
  font: inherit;
  font-size: 0.82rem;
  cursor: pointer;
}

.tag-chip:hover {
  border-color: color-mix(in srgb, var(--accent) 40%, var(--line));
  color: var(--ink);
}

.tag-chip.active {
  background: #eef6f3;
  border-color: color-mix(in srgb, var(--accent) 45%, var(--line));
  color: var(--accent);
  font-weight: 600;
}

.empty-hint {
  margin: 8px 0 0;
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}

.module-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: color-mix(in srgb, var(--panel) 92%, #f8f4eb);
  box-shadow: 0 1px 0 color-mix(in srgb, var(--line) 50%, transparent);
}

.module-card.off {
  opacity: 0.72;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}

.card-title h2 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 650;
}

.card-title .id {
  display: block;
  margin-top: 2px;
  font-size: 0.78rem;
}

.state-pill {
  flex-shrink: 0;
  font-size: 0.72rem;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid var(--line);
  text-transform: lowercase;
}

.state-pill.on {
  background: #eef6f3;
  color: var(--accent);
  border-color: color-mix(in srgb, var(--accent) 30%, var(--line));
}

.state-pill.off {
  background: #f5f1ea;
  color: var(--muted);
}

.summary {
  margin: 0;
  color: var(--muted);
  font-size: 0.9rem;
  line-height: 1.45;
  min-height: 2.6em;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.meta {
  font-size: 0.75rem;
  color: var(--muted);
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 2px 6px;
  background: #fff;
}

.meta.lock {
  color: var(--accent);
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.mini-tag {
  border: 0;
  background: #eef2ea;
  color: var(--ink);
  font: inherit;
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
}

.mini-tag:hover {
  background: #e2ebe4;
}

.card-foot {
  margin-top: auto;
  padding-top: 4px;
  display: flex;
  align-items: center;
  min-height: 32px;
  justify-content: space-between;
}
.card-foot .btn {
  margin-left: auto;
  font-size: 0.85rem;
  line-height: 1.25;
  padding: 4px 8px;
  border-radius: 4px;
  background: #eef2ea;
  color: var(--ink);
  cursor: pointer;
}
</style>
