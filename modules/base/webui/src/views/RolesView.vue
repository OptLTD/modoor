<template>
  <section class="roles-page">
    <p v-if="error" class="error">{{ error }}</p>

    <div class="roles-split">
      <!-- 左侧：角色列表 -->
      <aside class="roles-left panel">
        <header class="pane-head">
          <h1>{{ t('base.roles') }}</h1>
          <button type="button" class="btn primary" @click="showCreate = !showCreate">
            {{ showCreate ? t('base.collapse') : t('base.create') }}
          </button>
        </header>

        <form v-if="showCreate" class="create-form" @submit.prevent="onCreate">
          <label>Code <input v-model="form.code" required placeholder="admin" /></label>
          <label>Name <input v-model="form.name" required /></label>
          <label>
            App
            <select v-model="form.app_id">
              <option value="">(tenant-wide)</option>
              <option v-for="a in apps" :key="a.id" :value="a.id">{{ a.code }} — {{ a.name }}</option>
            </select>
          </label>
          <label>Description <input v-model="form.description" /></label>
          <button class="btn primary" type="submit">Create</button>
        </form>

        <ul class="role-list">
          <li
            v-for="r in roles"
            :key="r.id"
            class="role-item"
            :class="{ active: selectedId === r.id }"
            @click="selectRole(r.id)"
          >
            <div class="role-item-main">
              <strong>{{ r.name }}</strong>
              <code>{{ r.code }}</code>
            </div>
            <span class="ability-count muted">
              {{ t('base.nodes', { n: (roleNodes[r.id] || []).length }) }}
            </span>
          </li>
          <li v-if="!roles.length" class="muted empty">{{ t('base.noRoles') }}</li>
        </ul>
      </aside>

      <!-- 右侧：权限 + 分配 -->
      <main class="roles-right panel">
        <template v-if="selected">
          <header class="pane-head">
            <div>
              <h1>{{ selected.name }}</h1>
            </div>
            <div class="head-actions">
              <button type="button" class="btn" :disabled="saving" @click="selectAllModule">
                {{ t('base.selectAllVisible') }}
              </button>
              <button type="button" class="btn" :disabled="saving" @click="clearDraft">{{ t('base.clear') }}</button>
              <button
                type="button"
                class="btn primary"
                :disabled="saving || !dirty"
                @click="onSaveAbilities"
              >
                {{ saving ? t('base.saving') : t('base.saveAbilities') }}
              </button>
              <button
                type="button"
                class="btn danger"
                @click="onDelete(selected.id, selected.code)"
              >
                {{ t('base.delete') }}
              </button>
            </div>
          </header>

          <div class="perm-toolbar">
            <input
              v-model="permKeyword"
              type="search"
              class="perm-search"
              :placeholder="t('base.filterAbilities')"
            />
            <span class="muted">{{ t('base.selectedCount', { n: draftAbilities.length, total: flatCatalog.length }) }}</span>
          </div>

          <div class="perm-groups">
            <section
              v-for="g in filteredCatalog"
              :key="g.module_id"
              class="perm-group"
            >
              <header class="group-head">
                <label class="group-check">
                  <input
                    type="checkbox"
                    :checked="moduleAllChecked(g)"
                    @change="toggleModule(g, ($event.target as HTMLInputElement).checked)"
                  />
                  <strong>{{ moduleLabel(g) }}</strong>
                  <span class="muted">{{ g.module_id }}</span>
                </label>
              </header>
              <div class="ability-grid">
                <label
                  v-for="a in g.abilities"
                  :key="a"
                  class="ability-item"
                >
                  <input
                    type="checkbox"
                    :checked="draftSet.has(a)"
                    @change="toggleAbility(a, ($event.target as HTMLInputElement).checked)"
                  />
                  <span class="ability-name">{{ abilityLabel(g, a) }}</span>
                </label>
              </div>
            </section>
            <p v-if="!filteredCatalog.length" class="muted empty">{{ t('base.noAbilities') }}</p>
          </div>

          <section class="assign-block">
            <h2>{{ t('base.assignUsers') }}</h2>
            <form class="assign-form" @submit.prevent="onAssign">
              <select v-model="assign.user_id" required>
                <option v-for="u in users" :key="u.id" :value="u.id">
                  {{ u.username }} — {{ u.realname }}
                </option>
              </select>
              <button class="btn primary" type="submit">Assign</button>
            </form>
          </section>
        </template>

        <div v-else class="empty-right muted">
          {{ t('base.pickRole') }}
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  useI18n,
  localizedAppLabel,
  localizedEntityLabel,
  type ManifestI18n,
} from '@modoor/hooks'
import {
  assignRole,
  createRole,
  deleteRole,
  revokeRole,
  rolesBundle,
  setRoleNodes,
  type User,
} from '../api/base'

type Role = {
  id: string
  code: string
  name: string
  app_id?: string | null
  description?: string | null
}

type AbilityGroup = {
  module_id: string
  label: string
  i18n?: ManifestI18n
  abilities: string[]
}

const { t, locale } = useI18n()
const error = ref('')
const roles = ref<Role[]>([])
const users = ref<User[]>([])
const apps = ref<{ id: string; code: string; name: string }[]>([])
const assignments = ref<Record<string, { id: string; code: string }[]>>({})
const roleNodes = ref<Record<string, string[]>>({})
const catalog = ref<AbilityGroup[]>([])

const selectedId = ref('')
const draftAbilities = ref<string[]>([])
const savedSnapshot = ref('')
const saving = ref(false)
const showCreate = ref(false)
const permKeyword = ref('')
const form = reactive({ code: '', name: '', app_id: '', description: '' })
const assign = reactive({ user_id: 0 as number, role_id: '' })

const selected = computed(() => roles.value.find((r) => r.id === selectedId.value) || null)
const draftSet = computed(() => new Set(draftAbilities.value))
const dirty = computed(() => JSON.stringify([...draftAbilities.value].sort()) !== savedSnapshot.value)
const flatCatalog = computed(() => catalog.value.flatMap((g) => g.abilities))

const filteredCatalog = computed(() => {
  const q = permKeyword.value.trim().toLowerCase()
  if (!q) return catalog.value
  return catalog.value
    .map((g) => ({
      ...g,
      abilities: g.abilities.filter((a) => {
        const name = abilityLabel(g, a).toLowerCase()
        return (
          a.toLowerCase().includes(q) ||
          name.includes(q) ||
          g.module_id.toLowerCase().includes(q) ||
          moduleLabel(g).toLowerCase().includes(q)
        )
      }),
    }))
    .filter((g) => g.abilities.length)
})

function moduleLabel(g: AbilityGroup) {
  return localizedAppLabel({ label: g.label, i18n: g.i18n }, locale.value, g.label)
}

function abilityLabel(g: AbilityGroup, code: string) {
  return localizedEntityLabel(g.i18n, { id: code, label: code }, locale.value, code)
}

const holders = computed(() => {
  if (!selected.value) return []
  const rid = selected.value.id
  return users.value.filter((u) => (assignments.value[u.id] || []).some((r) => r.id === rid))
})

function appLabel(appId: string) {
  const a = apps.value.find((x) => x.id === appId)
  return a ? a.code : appId.slice(0, 8)
}

function selectRole(id: string) {
  selectedId.value = id
  assign.role_id = id
  const abs = [...(roleNodes.value[id] || [])].sort()
  draftAbilities.value = abs
  savedSnapshot.value = JSON.stringify(abs)
}

function toggleAbility(code: string, on: boolean) {
  const set = new Set(draftAbilities.value)
  if (on) set.add(code)
  else set.delete(code)
  draftAbilities.value = [...set].sort()
}

function moduleAllChecked(g: AbilityGroup) {
  return g.abilities.length > 0 && g.abilities.every((a) => draftSet.value.has(a))
}

function toggleModule(g: AbilityGroup, on: boolean) {
  const set = new Set(draftAbilities.value)
  for (const a of g.abilities) {
    if (on) set.add(a)
    else set.delete(a)
  }
  draftAbilities.value = [...set].sort()
}

function selectAllModule() {
  const set = new Set(draftAbilities.value)
  for (const g of filteredCatalog.value) {
    for (const a of g.abilities) set.add(a)
  }
  draftAbilities.value = [...set].sort()
}

function clearDraft() {
  draftAbilities.value = []
}

async function reload() {
  error.value = ''
  try {
    const res = await rolesBundle()
    roles.value = res.roles
    users.value = res.users
    apps.value = res.apps
    assignments.value = res.assignments
    roleNodes.value = res.role_nodes || {}
    catalog.value = res.ability_catalog?.modules || []
    if (!assign.user_id && users.value[0]) assign.user_id = users.value[0].id
    const keep = selectedId.value && roles.value.some((r) => r.id === selectedId.value)
    if (keep) selectRole(selectedId.value)
    else if (roles.value[0]) selectRole(roles.value[0].id)
    else {
      selectedId.value = ''
      draftAbilities.value = []
      savedSnapshot.value = '[]'
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

async function onCreate() {
  try {
    await createRole({
      code: form.code,
      name: form.name,
      app_id: form.app_id || undefined,
      description: form.description || undefined,
    })
    form.code = form.name = form.app_id = form.description = ''
    showCreate.value = false
    await reload()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

async function onDelete(id: string, code: string) {
  if (!confirm(`Delete role ${code}?`)) return
  try {
    await deleteRole(id)
    if (selectedId.value === id) selectedId.value = ''
    await reload()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

async function onSaveAbilities() {
  if (!selected.value) return
  saving.value = true
  error.value = ''
  try {
    const res = await setRoleNodes(selected.value.id, draftAbilities.value)
    roleNodes.value = {
      ...roleNodes.value,
      [selected.value.id]: res.nodes,
    }
    const abs = [...res.nodes].sort()
    draftAbilities.value = abs
    savedSnapshot.value = JSON.stringify(abs)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    saving.value = false
  }
}

async function onAssign() {
  if (!selected.value) return
  try {
    await assignRole(assign.user_id, selected.value.id)
    await reload()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

watch(selectedId, (id) => {
  if (id) assign.role_id = id
})

onMounted(reload)
</script>

<style scoped>
.roles-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.roles-split {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(240px, 320px) 1fr;
  gap: 12px;
}

.roles-left,
.roles-right {
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 14px 16px;
}

.pane-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-shrink: 0;
  margin-bottom: 12px;
}

.pane-head h1 {
  margin: 0;
  font-size: 1.2rem;
}

.pane-head .muted {
  margin: 4px 0 0;
  font-size: 0.85rem;
}

.head-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}

.create-form {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
  flex-shrink: 0;
}

.create-form label {
  display: grid;
  gap: 4px;
  font-size: 0.85rem;
}

.create-form input,
.create-form select,
.perm-search,
.assign-form select {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 7px 9px;
  font: inherit;
  background: #fff;
}

.role-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow: auto;
  flex: 1;
  min-height: 0;
}

.role-item {
  display: grid;
  gap: 2px;
  padding: 10px 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
}

.role-item:hover {
  background: #f8f4eb;
}

.role-item.active {
  background: #eef6f3;
  border-color: color-mix(in srgb, var(--accent) 35%, var(--line));
}

.role-item-main {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: baseline;
}

.role-item-main code,
.scope,
.ability-count {
  font-size: 0.78rem;
}

.empty,
.empty-right {
  padding: 24px 8px;
  text-align: center;
}

.empty-right {
  flex: 1;
  display: grid;
  place-items: center;
}

.perm-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.perm-search {
  width: min(280px, 100%);
}

.perm-groups {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.perm-group {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 10px 12px;
  background: color-mix(in srgb, var(--panel) 90%, #f8f4eb);
}

.group-head {
  margin-bottom: 8px;
}

.group-check {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.group-check .muted {
  font-size: 0.78rem;
}

.ability-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 6px 10px;
}

.ability-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
  cursor: pointer;
  min-width: 0;
}

.ability-name {
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
}

.assign-block {
  flex-shrink: 0;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.assign-block h2 {
  margin: 0 0 8px;
  font-size: 1rem;
}

.assign-form {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.assign-form select {
  flex: 1;
  min-width: 0;
}

.assignees {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

@media (max-width: 860px) {
  .roles-split {
    grid-template-columns: 1fr;
    overflow: auto;
  }
  .roles-left {
    max-height: 280px;
  }
}
</style>
