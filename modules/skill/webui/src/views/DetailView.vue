<template>
  <section class="panel">
    <p v-if="error" class="error">{{ error }}</p>
    <div v-if="skill" class="skill-detail">
      <div class="row-between">
        <h1>{{ skill.title }}</h1>
        <div class="row-actions">
          <RouterLink
            v-if="!skill.readonly"
            class="btn"
            :to="`/web/skill/${encodeURIComponent(skill.id)}/edit`"
          >
            {{ t('skill.edit') }}
          </RouterLink>
          <RouterLink class="btn" to="/web/skill">{{ t('skill.back') }}</RouterLink>
        </div>
      </div>
      <p class="muted">
        <code>{{ skill.id }}</code>
        · {{ skill.source }}{{ skill.readonly ? ` · ${t('skill.readonly')}` : '' }}
        <template v-if="skill.updated_at"> · {{ skill.updated_at }}</template>
      </p>
      <p v-if="skill.summary">{{ skill.summary }}</p>
      <p v-if="skill.when_to_use" class="muted">
        <strong>{{ t('skill.whenToUse') }}:</strong> {{ skill.when_to_use }}
      </p>
      <p v-if="skill.tools?.length" class="muted">
        <strong>{{ t('skill.tools') }}:</strong>
        <code v-for="tool in skill.tools" :key="String(tool)" style="margin-right: 0.35rem">
          {{ tool }}
        </code>
      </p>
      <p v-if="skill.readonly" class="muted">{{ t('skill.readonlyNotice') }}</p>
      <pre class="wiki-body">{{ skill.markdown || skill.content }}</pre>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from '@modoor/hooks'
import { getSkill, type SkillItem } from '../api/skill'

const { t } = useI18n()
const route = useRoute()
const skill = ref<SkillItem | null>(null)
const error = ref('')

function skillIdFromRoute() {
  return decodeURIComponent(String(route.params.id || ''))
}

async function load() {
  error.value = ''
  try {
    const res = await getSkill(skillIdFromRoute())
    skill.value = res.skill
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

watch(() => route.params.id, load)
onMounted(load)
</script>
