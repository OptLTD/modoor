<template>
  <section class="panel">
    <div class="ws-head row-between">
      <h1>{{ t('skill.title') }}</h1>
      <RouterLink class="btn primary" to="/web/skill/new">{{ t('skill.newCustom') }}</RouterLink>
    </div>
    <p class="muted">
      {{ t('skill.intro', { n: count }) }}
    </p>
    <div class="row-actions" style="margin-bottom: 0.75rem; gap: 0.5rem; flex-wrap: wrap">
      <label class="muted">
        {{ t('skill.source') }}
        <select v-model="source" @change="reload">
          <option value="">{{ t('skill.sourceAll') }}</option>
          <option value="module">{{ t('skill.sourceModule') }}</option>
          <option value="custom">{{ t('skill.sourceCustom') }}</option>
        </select>
      </label>
      <input
        v-model="q"
        class="filter-input"
        :placeholder="t('skill.searchPh')"
        @keyup.enter="reload"
      />
      <button class="btn" type="button" @click="reload">{{ t('skill.search') }}</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <table class="data">
      <thead>
        <tr>
          <th>{{ t('skill.colId') }}</th>
          <th>{{ t('skill.colTitle') }}</th>
          <th>{{ t('skill.colSource') }}</th>
          <th>{{ t('skill.colUpdated') }}</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in skills" :key="s.id">
          <td>
            <RouterLink :to="`/web/skill/${encodeURIComponent(s.id)}`">
              <code>{{ s.id }}</code>
            </RouterLink>
          </td>
          <td>{{ s.title }}</td>
          <td>
            <span :class="s.readonly ? 'badge muted' : 'badge'">
              {{ s.source }}{{ s.readonly ? ` · ${t('skill.readonly')}` : '' }}
            </span>
          </td>
          <td class="muted">{{ s.updated_at || '—' }}</td>
          <td class="row-actions">
            <RouterLink :to="`/web/skill/${encodeURIComponent(s.id)}`">{{ t('skill.view') }}</RouterLink>
            <template v-if="!s.readonly">
              <RouterLink :to="`/web/skill/${encodeURIComponent(s.id)}/edit`">{{ t('skill.edit') }}</RouterLink>
              <button class="btn danger" type="button" @click="onDelete(s)">{{ t('skill.delete') }}</button>
            </template>
          </td>
        </tr>
        <tr v-if="!skills.length">
          <td colspan="5" class="muted">{{ t('skill.empty') }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { registerShellSearch, useI18n } from '@modoor/hooks'
import { deleteSkill, listSkills, type SkillItem } from '../api/skill'

const { t } = useI18n()
const skills = ref<SkillItem[]>([])
const count = ref(0)
const error = ref('')
const source = ref('')
const q = ref('')

async function reload() {
  error.value = ''
  try {
    const res = await listSkills({
      source: source.value || undefined,
      q: q.value.trim() || undefined,
    })
    skills.value = res.items || []
    count.value = res.count || skills.value.length
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

async function onDelete(s: SkillItem) {
  if (s.readonly) return
  if (!confirm(t('skill.confirmDelete', { id: s.id }))) return
  try {
    await deleteSkill(s.id)
    await reload()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

let unregisterSearch: (() => void) | null = null

onMounted(() => {
  void reload()
  unregisterSearch = registerShellSearch('skill.catalog', (query) => {
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
.badge {
  display: inline-block;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  background: #e8f0fe;
  font-size: 0.85em;
}
.badge.muted {
  background: #f0f0f0;
}
.filter-input {
  min-width: 12rem;
}
</style>
