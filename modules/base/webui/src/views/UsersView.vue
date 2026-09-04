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
            :title="t('base.newTeam')"
            :disabled="!rootTeamId"
            @click="onAddTeam"
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
          ref="tableRef"
          :key="tableKey"
          :table="table"
          using="default"
          :hide-export="true"
          @toolbar-click="onToolbarClick"
        />
        <div v-else class="empty-right muted">{{ t('base.loadingUsers') }}</div>
      </main>
    </div>

    <div v-if="pwdOpen" class="modal-mask" @click.self="closePassword">
      <div class="modal pwd-modal">
        <header class="modal-head">
          <strong>{{ t('base.changePassword') }}</strong>
          <button type="button" class="link" @click="closePassword">{{ t('widget.close') }}</button>
        </header>
        <form class="form" @submit.prevent="submitPassword">
          <p v-if="pwdUserName" class="muted">{{ pwdUserName }}</p>
          <label>
            {{ t('base.newPassword') }}
            <input v-model="pwd1" type="password" autocomplete="new-password" />
          </label>
          <label>
            {{ t('base.confirmPassword') }}
            <input v-model="pwd2" type="password" autocomplete="new-password" />
          </label>
          <p v-if="pwdError" class="error">{{ pwdError }}</p>
          <div class="modal-actions pwd-actions">
            <button type="button" class="btn" @click="closePassword">{{ t('widget.cancel') }}</button>
            <button type="submit" class="btn primary" :disabled="pwdSaving">
              {{ pwdSaving ? t('widget.saving') : t('widget.save') }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="roleOpen" class="modal-mask" @click.self="closeRoles">
      <div class="modal pwd-modal">
        <header class="modal-head">
          <strong>{{ t('base.setRole') }}</strong>
          <button type="button" class="link" @click="closeRoles">{{ t('widget.close') }}</button>
        </header>
        <form class="form" @submit.prevent="submitRoles">
          <p v-if="roleUserName" class="muted">{{ roleUserName }}</p>
          <p v-if="!allRoles.length" class="muted">{{ t('base.noRolesToAssign') }}</p>
          <label v-for="r in allRoles" :key="r.id" class="role-check">
            <input
              type="checkbox"
              :checked="pickedRoleIds.includes(r.id)"
              @change="togglePickedRole(r.id, ($event.target as HTMLInputElement).checked)"
            />
            <span>{{ r.name }}</span>
            <code>{{ r.code }}</code>
          </label>
          <p v-if="roleError" class="error">{{ roleError }}</p>
          <div class="modal-actions pwd-actions">
            <button type="button" class="btn" @click="closeRoles">{{ t('widget.cancel') }}</button>
            <button type="submit" class="btn primary" :disabled="roleSaving">
              {{ roleSaving ? t('widget.saving') : t('widget.save') }}
            </button>
          </div>
        </form>
      </div>
    </div>

  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  fetchMe,
  fetchSchema,
  useI18n,
  type SchemaClick,
  type SchemaTable as SchemaTableData,
} from '@modoor/hooks'
import { SchemaTable } from '@modoor/widget/SchemaTable'
import {
  assignRole,
  createTeam,
  deleteTeam,
  fetchUserRoles,
  listTeamTree,
  revokeRole,
  updateTeam,
  updateUser,
  type TeamNode,
} from '../api/base'
import OrgTreeNode from '../components/OrgTreeNode.vue'

const { t } = useI18n()
const error = ref('')
const bootError = ref('')
const teamTree = ref<TeamNode[]>([])
const selectedTeamId = ref<number | null>(null)
const table = ref<SchemaTableData | null>(null)
const tableRef = ref<{ reload: () => void | Promise<void> } | null>(null)
const meUserId = ref<string | null>(null)

const pwdOpen = ref(false)
const pwdUserId = ref<string | null>(null)
const pwdUserName = ref('')
const pwd1 = ref('')
const pwd2 = ref('')
const pwdError = ref('')
const pwdSaving = ref(false)

const roleOpen = ref(false)
const roleSaving = ref(false)
const roleError = ref('')
const roleUserId = ref<number | null>(null)
const roleUserName = ref('')
const allRoles = ref<{ id: string; code: string; name: string }[]>([])
const pickedRoleIds = ref<string[]>([])
const savedRoleIds = ref<string[]>([])

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

function rowUserKey(row: Record<string, unknown>) {
  return String(row['basic.uukey'] ?? row.uukey ?? '').trim()
}

function rowUserName(row: Record<string, unknown>) {
  return String(row['basic.name'] || row['basic.realname'] || row['basic.username'] || '')
}

function isRowActive(row: Record<string, unknown>) {
  const v = row['basic.active']
  if (v === true || v === 'true' || v === 1 || v === '1') return true
  if (v === false || v === 'false' || v === 0 || v === '0') return false
  const state = row['basic.state']
  return state === 1 || state === '1'
}

function isCurrentUser(row: Record<string, unknown>) {
  if (meUserId.value == null) return false
  return rowUserKey(row) === meUserId.value
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
      createDefaults: (() => {
        const teamId = selectedTeamId.value ?? rootTeamId.value
        return teamId != null ? { 'basic.team_id': String(teamId) } : undefined
      })(),
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

async function onAddTeam() {
  if (rootTeamId.value == null) {
    error.value = t('base.noHeadTeam')
    return
  }
  const name = prompt(t('base.teamName'))
  if (!name?.trim()) return
  try {
    await createTeam({ name: name.trim() })
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

function onToolbarClick(payload: {
  click: SchemaClick
  keys: string[]
  rows: Record<string, unknown>[]
}) {
  const row = payload.rows[0]
  switch (payload.click.uukey) {
    case 'set_role':
      if (row) void onOpenRoles(row)
      return
    case 'set_pswd':
      if (row) onOpenPassword(row)
      return
    case 'enable':
      void onSetActiveRows(payload.rows, true)
      return
    case 'disable':
      void onSetActiveRows(payload.rows, false)
      return
  }
}

async function onSetActiveRows(targets: Record<string, unknown>[], next: boolean) {
  const rows = targets.filter((row) => {
    if (isCurrentUser(row) && !next) return false
    return next !== isRowActive(row)
  })
  if (!rows.length) {
    if (targets.some((row) => isCurrentUser(row) && !next)) {
      error.value = t('base.cannotDisableSelf')
    }
    return
  }
  const name = rows.length === 1 ? rowUserName(rows[0]) : String(rows.length)
  const ok = confirm(
    next ? t('base.confirmEnable', { name }) : t('base.confirmDisable', { name }),
  )
  if (!ok) return
  try {
    for (const row of rows) {
      const id = rowUserKey(row)
      if (id) await updateUser(id, { active: next })
    }
    await tableRef.value?.reload()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

function onOpenPassword(row: Record<string, unknown>) {
  const id = rowUserKey(row)
  if (!id) return
  pwdUserId.value = id
  pwdUserName.value = rowUserName(row)
  pwd1.value = ''
  pwd2.value = ''
  pwdError.value = ''
  pwdOpen.value = true
}

async function onOpenRoles(row: Record<string, unknown>) {
  const key = rowUserKey(row)
  if (!key) return
  roleError.value = ''
  roleUserName.value = rowUserName(row)
  roleOpen.value = true
  try {
    const res = await fetchUserRoles(key)
    roleUserId.value = res.user_id
    allRoles.value = res.roles || []
    const assigned = (res.assigned || []).map((r) => r.id)
    savedRoleIds.value = assigned
    pickedRoleIds.value = [...assigned]
  } catch (e) {
    roleError.value = e instanceof Error ? e.message : String(e)
    allRoles.value = []
    pickedRoleIds.value = []
    savedRoleIds.value = []
    roleUserId.value = null
  }
}

function closeRoles() {
  roleOpen.value = false
  roleUserId.value = null
  roleUserName.value = ''
  allRoles.value = []
  pickedRoleIds.value = []
  savedRoleIds.value = []
  roleError.value = ''
}

function togglePickedRole(id: string, on: boolean) {
  if (on) {
    if (!pickedRoleIds.value.includes(id)) pickedRoleIds.value = [...pickedRoleIds.value, id]
    return
  }
  pickedRoleIds.value = pickedRoleIds.value.filter((x) => x !== id)
}

async function submitRoles() {
  if (roleUserId.value == null) return
  roleSaving.value = true
  roleError.value = ''
  try {
    const current = new Set(savedRoleIds.value)
    const next = new Set(pickedRoleIds.value)
    for (const id of next) {
      if (!current.has(id)) await assignRole(roleUserId.value, id)
    }
    for (const id of current) {
      if (!next.has(id)) await revokeRole(roleUserId.value, id)
    }
    closeRoles()
  } catch (e) {
    roleError.value = e instanceof Error ? e.message : String(e)
  } finally {
    roleSaving.value = false
  }
}

function closePassword() {
  pwdOpen.value = false
  pwdUserId.value = null
  pwdUserName.value = ''
  pwd1.value = ''
  pwd2.value = ''
  pwdError.value = ''
}

async function submitPassword() {
  if (pwdUserId.value == null) return
  if (!pwd1.value) {
    pwdError.value = t('base.passwordRequired')
    return
  }
  if (pwd1.value !== pwd2.value) {
    pwdError.value = t('base.passwordMismatch')
    return
  }
  pwdSaving.value = true
  pwdError.value = ''
  try {
    await updateUser(pwdUserId.value, { password: pwd1.value })
    closePassword()
  } catch (e) {
    pwdError.value = e instanceof Error ? e.message : String(e)
  } finally {
    pwdSaving.value = false
  }
}

onMounted(async () => {
  try {
    const me = await fetchMe()
    meUserId.value = me.user?.uukey != null ? String(me.user.uukey) : null
  } catch {
    meUserId.value = null
  }
  await reload()
})
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

.pwd-modal {
  width: min(420px, 100%);
}

.pwd-actions {
  padding-bottom: 4px;
}

.role-check {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}

.role-check code {
  margin-left: auto;
  font-size: 0.78rem;
  color: var(--muted);
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
