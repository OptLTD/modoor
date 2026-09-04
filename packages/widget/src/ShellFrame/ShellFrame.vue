<template>
  <div class="shell" @click="closeMenus">
    <header class="top">
      <a class="shell-logo" href="/" aria-label="Modoor">
        <img :src="logoSrc" alt="" width="32" height="32" />
      </a>
      <div class="brand-wrap" :class="{ open: openMenu === 'brand' }" @click.stop>
        <button
          class="brand"
          type="button"
          aria-haspopup="listbox"
          :aria-expanded="openMenu === 'brand'"
          @click="toggleMenu('brand')"
        >
          {{ currentLabel }}
          <span class="caret">▾</span>
        </button>
        <div v-if="openMenu === 'brand'" class="switcher" role="listbox">
          <button
            v-for="m in switcherModules"
            :key="m.id"
            type="button"
            class="switcher-item"
            :class="{ active: m.id === activeModule }"
            role="option"
            @click="goModule(m)"
          >
            <span>{{ m.label }}</span>
          </button>
        </div>
      </div>
      <nav v-if="user && menus.length" class="nav">
        <RouterLink v-for="item in menus" :key="item.id" :to="item.path">{{ item.label }}</RouterLink>
      </nav>
      <div class="systray">
        <template v-if="user">
          <form class="shell-search-wrap" @click.stop @submit.prevent="onShellSearch">
            <input
              v-model="searchQ"
              type="search"
              class="shell-search"
              :placeholder="t('shell.search')"
              :aria-label="t('shell.searchAria')"
              @keydown.escape="searchQ = ''"
            />
          </form>

          <div
            class="systray-item"
            :class="{ open: openMenu === 'inbox' }"
            @click.stop
          >
            <button
              type="button"
              class="systray-btn"
              aria-haspopup="true"
              :aria-expanded="openMenu === 'inbox'"
              :aria-label="t('shell.inbox')"
              :title="t('shell.inbox')"
              @click="toggleMenu('inbox')"
            >
              <svg class="systray-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M6 9a6 6 0 1 1 12 0c0 3.2 1.2 4.8 2 6H4c.8-1.2 2-2.8 2-6" />
                <path d="M10 19a2 2 0 0 0 4 0" />
              </svg>
              <span v-if="inboxCount > 0" class="systray-badge">{{ inboxCount }}</span>
            </button>
            <div v-if="openMenu === 'inbox'" class="systray-menu wide" role="menu">
              <div class="systray-menu-header">
                <div class="name">{{ t('shell.inbox') }}</div>
              </div>
              <a
                v-for="msg in inbox"
                :key="msg.id"
                :href="msg.href || '#'"
                role="menuitem"
                @click="closeMenus"
              >
                {{ msg.title }}
              </a>
              <div v-if="!inbox.length" class="systray-empty">{{ t('shell.inboxEmpty') }}</div>
            </div>
          </div>

          <div
            v-if="tenants.length > 1"
            class="systray-item"
            :class="{ open: openMenu === 'tenant' }"
            @click.stop
          >
            <button
              type="button"
              class="systray-btn"
              aria-haspopup="true"
              :aria-expanded="openMenu === 'tenant'"
              :aria-label="t('shell.tenant')"
              :title="t('shell.tenant')"
              @click="toggleMenu('tenant')"
            >
              <svg class="systray-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
                <path d="M3 21h18" />
                <path d="M5 21V8l7-4 7 4v13" />
                <path d="M9 21v-6h6v6" />
              </svg>
              <span class="tenant-label">{{ tenantName }}</span>
            </button>
            <div v-if="openMenu === 'tenant'" class="systray-menu" role="menu">
              <div class="systray-menu-header">
                <div class="name">{{ t('shell.tenant') }}</div>
                <div class="sub">{{ t('shell.tenantSub') }}</div>
              </div>
              <button
                v-for="tn in tenants"
                :key="tn.id"
                type="button"
                class="menu-link"
                :class="{ active: tn.id === tenantId }"
                role="menuitem"
                @click="selectTenant(tn)"
              >
                {{ tn.name }}
              </button>
            </div>
          </div>

          <div
            class="systray-item"
            :class="{ open: openMenu === 'avatar' }"
            @click.stop
          >
            <button
              type="button"
              class="systray-btn"
              aria-haspopup="true"
              :aria-expanded="openMenu === 'avatar'"
              aria-label="User menu"
              :title="user.realname || user.username"
              @click="toggleMenu('avatar')"
            >
              <span class="avatar">{{ userInitials }}</span>
            </button>
            <div v-if="openMenu === 'avatar'" class="systray-menu" role="menu">
              <div class="systray-menu-header">
                <div class="name">{{ user.realname || user.username }}</div>
                <div class="sub">{{ user.username }} · {{ tenantName }}</div>
              </div>
              <div class="systray-menu-header lang-head">
                <div class="sub">{{ t('shell.language') }}</div>
              </div>
              <button
                v-for="loc in SUPPORTED_LOCALES"
                :key="loc.code"
                type="button"
                class="menu-link"
                :class="{ active: locale === loc.code }"
                role="menuitem"
                @click="onSetLocale(loc.code)"
              >
                {{ loc.label }}
              </button>
              <div class="sep" />
              <button type="button" class="menu-link" role="menuitem" @click="onLogout">
                {{ t('shell.logout') }}
              </button>
            </div>
          </div>
        </template>
        <a v-else class="systray-login" :href="loginHref">{{ t('shell.login') }}</a>
      </div>
    </header>
    <main class="main">
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  fetchProfile,
  switchTenant,
  logout as apiLogout,
  fetchShellCatalog,
  shellLoginUrl,
  runShellSearch,
  useI18n,
  setLocale,
  SUPPORTED_LOCALES,
  localizedAppLabel,
  localizedEntityLabel,
  type AuthUser,
  type ShellModule,
  type LocaleCode,
} from '@modoor/hooks'

type InboxMessage = { id: string; title: string; href?: string }
type TenantOption = { id: string; name: string }
type OpenMenu = 'brand' | 'inbox' | 'tenant' | 'avatar' | null

const props = defineProps<{
  /** Current module id (base / wiki / sale / …) */
  moduleId: string
}>()

const { t, locale } = useI18n()
const router = useRouter()
const route = useRoute()
const user = ref<AuthUser | null>(null)
const modules = ref<ShellModule[]>([])
const tenantId = ref('')
const tenants = ref<TenantOption[]>([])
const inbox = ref<InboxMessage[]>([])
const openMenu = ref<OpenMenu>(null)
const activeModule = ref(props.moduleId)
const searchQ = ref('')
const logoSrc = '/logo.png'

const currentLabel = computed(() => {
  const hit = modules.value.find((m) => m.id === activeModule.value)
  return localizedAppLabel(hit, locale.value, 'Modoor')
})

const menus = computed(() => {
  const hit = modules.value.find((m) => m.id === activeModule.value)
  const list = hit?.menus || []
  return list.map((item) => ({
    ...item,
    label: localizedEntityLabel(hit?.i18n, item, locale.value, item.label),
  }))
})

const switcherModules = computed(() =>
  modules.value.map((m) => ({
    ...m,
    label: localizedAppLabel(m, locale.value, m.label),
  })),
)

const tenantName = computed(() => {
  const hit = tenants.value.find((tn) => tn.id === tenantId.value)
  return hit?.name || tenantId.value || '—'
})

const inboxCount = computed(() => inbox.value.length)

const userInitials = computed(() => {
  const name = (user.value?.realname || user.value?.username || '?').trim()
  const parts = name.split(/\s+/).filter(Boolean)
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase()
  }
  return name.slice(0, 2).toUpperCase()
})

const loginHref = computed(() => shellLoginUrl())

function detectActive() {
  activeModule.value = props.moduleId
  const path = route.path
  for (const m of modules.value) {
    if (m.path && path.startsWith(m.path)) {
      activeModule.value = m.id
      break
    }
  }
}

function closeMenus() {
  openMenu.value = null
}

function toggleMenu(name: Exclude<OpenMenu, null>) {
  openMenu.value = openMenu.value === name ? null : name
}

async function refresh() {
  try {
    const profile = await fetchProfile()
    user.value = profile.user
    const cat = await fetchShellCatalog()
    modules.value = cat.modules || []
    const tid = String(profile.user.tenant ?? cat.tenant?.id ?? '')
    tenantId.value = tid
    const fromProfile = (profile.user.tenants || []).map((tn) => ({
      id: String(tn.id),
      name: String(tn.name),
    }))
    tenants.value =
      fromProfile.length > 0
        ? fromProfile
        : [
            {
              id: tid,
              name: String(cat.tenant?.name || tid),
            },
          ]
    inbox.value = []
    detectActive()
  } catch {
    user.value = null
    modules.value = []
    tenants.value = []
    inbox.value = []
  }
}

function goModule(m: ShellModule) {
  closeMenus()
  activeModule.value = m.id
  if (m.id === props.moduleId) {
    const local = m.menus?.[0]?.path || m.path
    if (local) router.push(local)
    return
  }
  if (m.href && /^https?:\/\//i.test(m.href)) {
    location.href = m.href
    return
  }
  if (m.path) router.push(m.path)
}

async function selectTenant(tn: TenantOption) {
  if (tn.id === tenantId.value) {
    closeMenus()
    return
  }
  closeMenus()
  await switchTenant(tn.id)
  location.reload()
}

function onShellSearch() {
  closeMenus()
  runShellSearch(searchQ.value.trim(), {
    path: route.path,
    moduleId: activeModule.value,
  })
}

function onSetLocale(code: LocaleCode) {
  setLocale(code)
  closeMenus()
}

async function onLogout() {
  closeMenus()
  await apiLogout()
  user.value = null
  location.href = shellLoginUrl()
}

watch(() => route.path, () => {
  detectActive()
  closeMenus()
})
watch(() => props.moduleId, detectActive)
onMounted(refresh)
</script>
