<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

export type SelectOption = {
  label: string
  value: string
}

const props = withDefaults(
  defineProps<{
    modelValue?: string | string[]
    options: SelectOption[]
    multiple?: boolean
    disabled?: boolean
    placeholder?: string
    clearable?: boolean
  }>(),
  {
    modelValue: '',
    multiple: false,
    disabled: false,
    placeholder: '请选择',
    clearable: true,
  },
)

const emit = defineEmits<{
  'update:modelValue': [string | string[]]
}>()

const open = ref(false)
const rootEl = ref<HTMLElement | null>(null)
const triggerEl = ref<HTMLElement | null>(null)
const panelEl = ref<HTMLElement | null>(null)
const panelStyle = ref<Record<string, string>>({})

const selected = computed<string[]>(() => {
  const v = props.modelValue
  if (props.multiple) {
    if (Array.isArray(v)) return v.map(String).filter(Boolean)
    if (typeof v === 'string' && v.trim()) {
      return v.split(/[,\n]/).map((s) => s.trim()).filter(Boolean)
    }
    return []
  }
  if (Array.isArray(v)) return v[0] ? [String(v[0])] : []
  return v ? [String(v)] : []
})

const displayText = computed(() => {
  if (!selected.value.length) return ''
  if (props.multiple) {
    return selected.value
      .map((val) => props.options.find((o) => o.value === val)?.label || val)
      .join('、')
  }
  const hit = props.options.find((o) => o.value === selected.value[0])
  return hit?.label || selected.value[0] || ''
})

function emitValue(vals: string[]) {
  if (props.multiple) emit('update:modelValue', vals)
  else emit('update:modelValue', vals[0] || '')
}

function isSelected(val: string) {
  return selected.value.includes(val)
}

function pick(opt: SelectOption) {
  if (props.disabled) return
  if (props.multiple) {
    const next = isSelected(opt.value)
      ? selected.value.filter((v) => v !== opt.value)
      : [...selected.value, opt.value]
    emitValue(next)
  } else {
    emitValue([opt.value])
    open.value = false
  }
}

function clear(e?: Event) {
  e?.stopPropagation()
  if (props.disabled) return
  emitValue([])
}

function updatePanelPos() {
  const el = triggerEl.value
  if (!el) return
  const r = el.getBoundingClientRect()
  const maxH = 220
  const spaceBelow = window.innerHeight - r.bottom - 8
  const placeUp = spaceBelow < 120 && r.top > spaceBelow
  panelStyle.value = {
    position: 'fixed',
    left: `${Math.max(8, r.left)}px`,
    width: `${Math.max(r.width, 140)}px`,
    zIndex: '70',
    ...(placeUp
      ? {
          bottom: `${window.innerHeight - r.top + 4}px`,
          top: 'auto',
          maxHeight: `${Math.min(maxH, r.top - 8)}px`,
        }
      : {
          top: `${r.bottom + 4}px`,
          bottom: 'auto',
          maxHeight: `${Math.min(maxH, spaceBelow)}px`,
        }),
  }
}

async function toggle() {
  if (props.disabled) return
  open.value = !open.value
  if (open.value) {
    await nextTick()
    updatePanelPos()
  }
}

function onDocPointer(e: Event) {
  const t = e.target as Node
  if (rootEl.value?.contains(t)) return
  if (panelEl.value?.contains(t)) return
  open.value = false
}

function onScrollOrResize() {
  if (open.value) updatePanelPos()
}

watch(open, (v) => {
  if (v) {
    window.addEventListener('scroll', onScrollOrResize, true)
    window.addEventListener('resize', onScrollOrResize)
  } else {
    window.removeEventListener('scroll', onScrollOrResize, true)
    window.removeEventListener('resize', onScrollOrResize)
  }
})

onMounted(() => {
  document.addEventListener('mousedown', onDocPointer)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocPointer)
  window.removeEventListener('scroll', onScrollOrResize, true)
  window.removeEventListener('resize', onScrollOrResize)
})
</script>

<template>
  <div ref="rootEl" class="select-box" :class="{ disabled }">
    <div
      ref="triggerEl"
      class="select-trigger"
      :class="{ disabled }"
      role="button"
      tabindex="0"
      @click="toggle"
      @keydown.enter.prevent="toggle"
      @keydown.space.prevent="toggle"
    >
      <span v-if="multiple && selected.length" class="tags">
        <span v-for="val in selected" :key="val" class="tag">
          {{ options.find((o) => o.value === val)?.label || val }}
          <button
            type="button"
            class="tag-x"
            :disabled="disabled"
            @click.stop="pick({ label: '', value: val })"
          >
            ×
          </button>
        </span>
      </span>
      <span v-else-if="displayText" class="value truncate">{{ displayText }}</span>
      <span v-else class="placeholder truncate">{{ placeholder }}</span>
      <span class="trailing">
        <button
          v-if="clearable && selected.length && !disabled"
          type="button"
          class="clear-btn"
          title="清除"
          @click.stop="clear"
        >
          ×
        </button>
        <svg class="chevron" :class="{ open }" width="12" height="12" viewBox="0 0 16 16" fill="none">
          <path
            d="M4 6l4 4 4-4"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </span>
    </div>

    <Teleport to="body">
      <div v-if="open" ref="panelEl" class="select-panel" :style="panelStyle">
        <button
          v-for="opt in options"
          :key="opt.value"
          type="button"
          class="select-option"
          :class="{ active: isSelected(opt.value) }"
          @click="pick(opt)"
        >
          <span v-if="multiple" class="check" :class="{ on: isSelected(opt.value) }">
            <svg v-if="isSelected(opt.value)" width="10" height="10" viewBox="0 0 16 16" fill="none">
              <path
                d="M3.5 8.5l3 3 6-6.5"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </span>
          <span class="truncate">{{ opt.label }}</span>
        </button>
        <div v-if="!options.length" class="empty">暂无选项</div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.select-box {
  width: 100%;
}
.select-trigger {
  display: flex;
  width: 100%;
  min-height: 32px;
  align-items: center;
  gap: 6px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: #fff;
  padding: 4px 8px;
  text-align: left;
  font: inherit;
  font-size: 0.875rem;
  color: var(--ink);
  cursor: pointer;
  box-sizing: border-box;
}
.select-trigger:hover:not(.disabled) {
  border-color: color-mix(in srgb, var(--accent) 35%, var(--line));
}
.select-trigger:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--accent) 35%, transparent);
  outline-offset: 0;
  border-color: var(--accent);
}
.select-trigger.disabled,
.select-box.disabled .select-trigger {
  cursor: not-allowed;
  background: #f8f4eb;
  color: var(--muted);
}
.placeholder {
  flex: 1;
  min-width: 0;
  color: var(--muted);
}
.value {
  flex: 1;
  min-width: 0;
}
.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tags {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-wrap: wrap;
  gap: 4px;
}
.tag {
  display: inline-flex;
  max-width: 100%;
  align-items: center;
  gap: 2px;
  border-radius: 4px;
  background: #eef6f3;
  padding: 1px 6px;
  font-size: 0.75rem;
  color: var(--accent);
}
.tag-x {
  border: 0;
  background: transparent;
  color: color-mix(in srgb, var(--accent) 55%, #fff);
  line-height: 1;
  cursor: pointer;
  padding: 0;
  font: inherit;
}
.tag-x:hover {
  color: var(--accent);
}
.trailing {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 2px;
  color: var(--muted);
}
.clear-btn {
  display: inline-flex;
  height: 16px;
  width: 16px;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 999px;
  background: transparent;
  font-size: 12px;
  line-height: 1;
  color: var(--muted);
  cursor: pointer;
  padding: 0;
}
.clear-btn:hover {
  background: color-mix(in srgb, var(--line) 60%, #fff);
  color: var(--ink);
}
.chevron {
  transition: transform 0.15s ease;
}
.chevron.open {
  transform: rotate(180deg);
}
</style>

<style>
.select-panel {
  overflow: auto;
  border-radius: 8px;
  border: 1px solid var(--line, #d9d0c0);
  background: var(--panel, #fffdf8);
  box-shadow: var(--shadow, 0 12px 40px rgba(40, 30, 10, 0.08));
  padding: 4px;
}
.select-option {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  padding: 7px 8px;
  text-align: left;
  font: inherit;
  font-size: 0.8125rem;
  color: var(--ink, #1c1914);
  cursor: pointer;
}
.select-option:hover {
  background: #f3f8f5;
}
.select-option.active {
  background: #eef6f3;
  color: var(--accent, #0f6a5a);
}
.select-option .check {
  display: inline-flex;
  height: 14px;
  width: 14px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 3px;
  border: 1px solid var(--line, #d9d0c0);
  background: #fff;
  color: #fff;
}
.select-option .check.on {
  border-color: var(--accent, #0f6a5a);
  background: var(--accent, #0f6a5a);
}
.select-panel .empty {
  padding: 12px 8px;
  text-align: center;
  font-size: 0.75rem;
  color: var(--muted, #6b6458);
}
.select-panel .truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
