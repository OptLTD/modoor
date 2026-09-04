<template>
  <PreviewPane v-if="asset" :asset="asset" class="detail-preview" />
  <p v-else-if="error" class="error">{{ error }}</p>
  <p v-else class="muted loading">{{ t('doc.loading') }}</p>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from '@modoor/hooks'
import { getAsset, type DocAsset } from '../api/doc'
import PreviewPane from '../components/PreviewPane.vue'

const { t } = useI18n()
const route = useRoute()
const asset = ref<DocAsset | null>(null)
const error = ref('')

function assetId() {
  return decodeURIComponent(String(route.params.id || ''))
}

async function load() {
  error.value = ''
  asset.value = null
  try {
    const res = await getAsset(assetId())
    asset.value = res.asset
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

watch(() => route.params.id, load)
onMounted(load)
</script>

<style scoped>
.detail-preview {
  flex: 1;
  min-height: 0;
  margin: -4px -6px;
  padding: 0;
}

.loading,
.error {
  padding: 24px 8px;
}
</style>
