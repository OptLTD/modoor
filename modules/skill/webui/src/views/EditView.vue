<template>
  <section class="panel">
    <h1>{{ isNew ? t('skill.newCustom') : t('skill.editCustom') }}</h1>
    <p class="muted">{{ t('skill.editHint') }}</p>
    <p v-if="error" class="error">{{ error }}</p>
    <form class="form" @submit.prevent="onSave">
      <label>
        Skill key
        <input v-model="form.skill_key" required pattern="[a-z][a-z0-9_]*" :readonly="!isNew" />
      </label>
      <label>Title <input v-model="form.title" required /></label>
      <label>Summary <textarea v-model="form.summary" rows="2" /></label>
      <label>{{ t('skill.whenToUse') }} <textarea v-model="form.when_to_use" rows="3" /></label>
      <label>
        {{ t('skill.toolsLabel') }}
        <input v-model="toolsText" placeholder="wiki.get_page, wiki.list_pages" />
      </label>
      <label>{{ t('skill.boundariesLabel') }} <textarea v-model="form.boundaries" rows="2" /></label>
      <label>{{ t('skill.contentLabel') }} <textarea v-model="form.content" rows="14" /></label>
      <div class="modal-actions">
        <RouterLink class="btn" to="/web/skill">{{ t('skill.cancel') }}</RouterLink>
        <button class="btn primary" type="submit" :disabled="saving">{{ t('skill.save') }}</button>
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from '@modoor/hooks'
import { getSkill, saveSkill } from '../api/skill'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const error = ref('')
const saving = ref(false)
const recordId = ref<string | undefined>()
const toolsText = ref('')
const form = reactive({
  skill_key: '',
  title: '',
  summary: '',
  when_to_use: '',
  content: '',
  boundaries: '',
})
const isNew = computed(() => route.name === 'skill.new' || route.path.endsWith('/new'))

function parseTools(raw: string): string[] {
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

async function boot() {
  if (isNew.value) return
  try {
    const id = decodeURIComponent(String(route.params.id || ''))
    const res = await getSkill(id)
    if (res.skill.readonly) {
      error.value = t('skill.readonlyError')
      return
    }
    recordId.value = res.skill.record_id
    form.skill_key = res.skill.skill_key
    form.title = res.skill.title
    form.summary = res.skill.summary || ''
    form.when_to_use = res.skill.when_to_use || ''
    form.content = res.skill.content || ''
    form.boundaries = res.skill.boundaries || ''
    toolsText.value = (res.skill.tools || []).map(String).join(', ')
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

async function onSave() {
  saving.value = true
  error.value = ''
  try {
    const res = await saveSkill({
      skill_key: form.skill_key,
      title: form.title,
      summary: form.summary,
      when_to_use: form.when_to_use,
      content: form.content,
      boundaries: form.boundaries,
      tools: parseTools(toolsText.value),
      record_id: recordId.value,
    })
    router.push(`/web/skill/${encodeURIComponent(res.skill.id)}`)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    saving.value = false
  }
}

onMounted(boot)
</script>
