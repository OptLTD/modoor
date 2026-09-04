<template>
  <section class="users-page">
    <p v-if="error" class="error">{{ error }}</p>

    <div class="users-split">
      <aside class="users-left panel">
        <header class="pane-head">
          <h1>{{ t('base.org') }}</h1>
          <button
            type="button"
            class="btn primary"
            :title="t('base.newChildTeam')"
            :disabled="!rootTeamId"
            @click="onAddTeam(selectedTeamId ?? rootTeamId)"
          >
            {{ t('base.newTeam') }}
          </button>
        </header>

        <div class="org-tree">
          <button
            type="button"
            class="org-item"
            :class="{ active: selectedTeamId === null }"
            @click="selectTeam(null)"
          >
            {{ t('base.allUsers') }}
          </button>
          <OrgTreeNode
            v-for="node in teamTree"
            :key="node.id"
            :node="node"
            :depth="0"
            :active-id="selectedTeamId"
            @select="selectTeam"
            @add-child="onAddTeam"
            @rename="onRenameTeam"
            @remove="onDeleteTeam"
          />
          <p v-if="!teamTree.length" class="muted empty">{{ t('base.noTeams') }}</p>
        </div>
      </aside>

      <main class="users-right panel">
        <header class="pane-head">
          <div>
            <h1>{{ t('base.users') }}</h1>
            <p class="muted">{{ teamTitle }}</p>
          </div>
        </header>

        <p v-if="bootError" class="error">{{ bootError }}</p>
        <SchemaTable
          v-if="table"
          :key="tableKey"
          :table="table"
          using="default"
        />
        <div v-else class="empty-right muted">{{ t('base.loadingUsers') }}</div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { fetchSchema, useI18n, type SchemaTable as SchemaTableData } from '@modoor/hooks'
import { SchemaTable } from '@modoor/widget/SchemaTable'
import {
  createTeam,
  deleteTeam,
  listTeamTree,
  updateTeam,
  type TeamNode,
} from '../api/base'
import OrgTreeNode from '../components/OrgTreeNode.vue'

const { t } = useI18n()
const error = ref('')
const bootError = ref('')
const teamTree = ref<TeamNode[]>([])
const selectedTeamId = ref<number | null>(null)
const table = ref<SchemaTableData | null>(null)

const rootTeamId = computed(() => teamTree.value[0]?.id ?? null)

const teamTitle = computed(() => {
  if (selectedTeamId.value === null) return t('base.allTeams')
  return findTeamName(teamTree.value, selectedTeamId.value) || t('base.team')
})

const tableKey = computed(() => `users-${selectedTeamId.value ?? 'all'}`)

function findTeamName(nodes: TeamNode[], id: number): string | null {
  for (const n of nodes) {
    if (n.id === id) return n.name
    const child = findTeamName(n.children || [], id)
    if (child) return child
  }
  return null
}

function collectTeamIds(node: TeamNode): number[] {
  return [node.id, ...(node.children || []).flatMap(collectTeamIds)]
}

function findNode(nodes: TeamNode[], id: number): TeamNode | null {
  for (const n of nodes) {
    if (n.id === id) return n
    const child = findNode(n.children || [], id)
    if (child) return child
  }
  return null
}

function selectTeam(id: number | null) {
  selectedTeamId.value = id
}

function teamQuery(): Record<string, unknown> | undefined {
  if (selectedTeamId.value == null) return undefined
  const node = findNode(teamTree.value, selectedTeamId.value)
  if (!node) return { 'basic.team_id': selectedTeamId.value }
  const ids = collectTeamIds(node)
  // 与 buildListQuery 一致：field:OP → parse_query
  return { 'basic.team_id:IN': ids }
}

async function bootTable() {
  bootError.value = ''
  try {
    const res = await fetchSchema('base.user', 'default')
    table.value = {
      ...res.table,
      model: res.model,
      using: res.using,
      title: res.table.title || t('base.usersList'),
      request: {
        ...(res.table.request || {}),
        query: teamQuery(),
      },
      createDefaults:
        selectedTeamId.value != null
          ? { 'basic.team_id': selectedTeamId.value, 'basic.active': 'true' }
          : { 'basic.active': 'true' },
    }
  } catch (e) {
    bootError.value = e instanceof Error ? e.message : String(e)
    table.value = null
  }
}

async function reloadTeams() {
  const res = await listTeamTree()
  teamTree.value = res.tree || []
}

async function reload() {
  error.value = ''
  try {
    await reloadTeams()
    await bootTable()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

watch(selectedTeamId, () => {
  void bootTable()
})

async function onAddTeam(parentId: number | null) {
  if (parentId == null) {
    error.value = t('base.pickParent')
    return
  }
  const name = prompt(t('base.childName'))
  if (!name?.trim()) return
  try {
    await createTeam({ name: name.trim(), parent: parentId })
    await reloadTeams()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

async function onRenameTeam(node: TeamNode) {
  const name = prompt(t('base.renameTeam'), node.name)
  if (!name?.trim() || name.trim() === node.name) return
  try {
    await updateTeam(node.id, { name: name.trim() })
    await reloadTeams()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

async function onDeleteTeam(node: TeamNode) {
  if (!confirm(t('base.confirmDeleteTeam', { name: node.name }))) return
  try {
    await deleteTeam(node.id)
    if (selectedTeamId.value === node.id) selectedTeamId.value = null
    await reload()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

onMounted(reload)
</script>

<style scoped>
.users-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.users-split {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(240px, 320px) 1fr;
  gap: 12px;
}

.users-left,
.users-right {
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

.org-tree {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.org-item {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 4px;
  border: 0;
  background: transparent;
  border-radius: 6px;
  padding: 8px 10px;
  cursor: pointer;
  font: inherit;
  color: inherit;
  text-align: left;
  margin-bottom: 4px;
}

.org-item:hover {
  background: #f8f4eb;
}

.org-item.active {
  background: #eef6f3;
  color: var(--accent);
  font-weight: 600;
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

.users-right :deep(.table-wrap) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.users-right :deep(.toolbar) {
  padding: 10px 0px;
}

@media (max-width: 800px) {
  .users-split {
    grid-template-columns: 1fr;
  }
  .users-left {
    max-height: 240px;
  }
}
</style>
