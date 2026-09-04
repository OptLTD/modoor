<template>
  <div class="preview-pane">
    <p v-if="loading" class="muted">{{ t('doc.previewLoading') }}</p>
    <p v-else-if="error" class="error">{{ error }}</p>

    <template v-else-if="kind === 'image'">
      <img class="preview-img" :src="contentSrc" :alt="asset.filename" />
    </template>

    <template v-else-if="kind === 'pdf' || kind === 'html'">
      <iframe class="preview-frame" :src="contentSrc" title="preview" />
    </template>

    <template v-else-if="kind === 'text'">
      <pre class="preview-pre">{{ textBody }}</pre>
    </template>

    <template v-else-if="kind === 'xlsx'">
      <div class="sheet-bar">
        <button
          v-for="(name, i) in sheetNames"
          :key="name"
          type="button"
          class="btn"
          :class="{ primary: i === sheetIndex }"
          @click="sheetIndex = i"
        >
          {{ name }}
        </button>
      </div>
      <div class="sheet-wrap" v-html="sheetHtml" />
    </template>

    <template v-else-if="kind === 'docx'">
      <div class="docx-html" v-html="docxHtml" />
    </template>

    <template v-else-if="kind === 'pptx'">
      <div class="pptx-nav">
        <button type="button" class="btn" :disabled="slideIndex <= 0" @click="slideIndex--">{{ t('doc.prevSlide') }}</button>
        <span class="muted">{{ slideIndex + 1 }} / {{ slides.length || 1 }}</span>
        <button
          type="button"
          class="btn"
          :disabled="slideIndex >= slides.length - 1"
          @click="slideIndex++"
        >
          {{ t('doc.nextSlide') }}
        </button>
      </div>
      <pre class="preview-pre slide">{{ slides[slideIndex] || t('doc.emptySlide') }}</pre>
    </template>

    <template v-else-if="kind === 'legacy'">
      <div class="fallback">
        <p>{{ t('doc.legacyHint') }}</p>
        <a class="btn primary" :href="downloadSrc" target="_blank" rel="noopener">{{ t('doc.download') }}</a>
        <pre v-if="asset.text" class="preview-pre">{{ asset.text }}</pre>
      </div>
    </template>

    <template v-else>
      <div class="fallback">
        <p>{{ t('doc.unsupportedPreview', { type: asset.mime_type || asset.ext || 'unknown' }) }}</p>
        <a class="btn primary" :href="downloadSrc" target="_blank" rel="noopener">{{ t('doc.download') }}</a>
        <pre v-if="asset.text" class="preview-pre">{{ asset.text }}</pre>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import * as XLSX from 'xlsx'
import mammoth from 'mammoth'
import JSZip from 'jszip'
import {
  contentUrl,
  fetchContentBlob,
  type DocAsset,
} from '../api/doc'
import { useI18n } from '@modoor/hooks'

const props = defineProps<{ asset: DocAsset }>()
const { t } = useI18n()

const loading = ref(false)
const error = ref('')
const textBody = ref('')
const sheetNames = ref<string[]>([])
const sheetHtmls = ref<string[]>([])
const sheetIndex = ref(0)
const docxHtml = ref('')
const slides = ref<string[]>([])
const slideIndex = ref(0)

const ext = computed(() => (props.asset.ext || props.asset.filename.split('.').pop() || '').toLowerCase())
const mime = computed(() => (props.asset.mime_type || '').toLowerCase())

const kind = computed(() => {
  const e = ext.value
  const m = mime.value
  if (m.startsWith('image/') || ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(e)) return 'image'
  if (m === 'application/pdf' || e === 'pdf') return 'pdf'
  if (m === 'text/html' || e === 'html' || e === 'htm') return 'html'
  if (
    m.startsWith('text/') ||
    ['txt', 'md', 'markdown', 'csv', 'json', 'log', 'xml'].includes(e)
  ) {
    return 'text'
  }
  if (e === 'xlsx' || e === 'xls' || m.includes('spreadsheetml')) return 'xlsx'
  if (e === 'docx' || m.includes('wordprocessingml')) return 'docx'
  if (e === 'pptx' || m.includes('presentationml')) return 'pptx'
  if (e === 'doc' || e === 'ppt') return 'legacy'
  return 'other'
})

const contentSrc = computed(() => contentUrl(props.asset.id))
const downloadSrc = computed(() => contentUrl(props.asset.id, true))
const sheetHtml = computed(() => sheetHtmls.value[sheetIndex.value] || '')

async function load() {
  loading.value = true
  error.value = ''
  textBody.value = ''
  sheetNames.value = []
  sheetHtmls.value = []
  sheetIndex.value = 0
  docxHtml.value = ''
  slides.value = []
  slideIndex.value = 0

  try {
    const k = kind.value
    if (k === 'image' || k === 'pdf' || k === 'html' || k === 'legacy' || k === 'other') {
      if ((k === 'legacy' || k === 'other') && props.asset.text) {
        /* text already shown */
      }
      return
    }
    if (k === 'text') {
      if (props.asset.text) {
        textBody.value = props.asset.text
        return
      }
      const blob = await fetchContentBlob(props.asset.id)
      textBody.value = await blob.text()
      return
    }
    const blob = await fetchContentBlob(props.asset.id)
    const buf = await blob.arrayBuffer()
    if (k === 'xlsx') {
      const wb = XLSX.read(buf, { type: 'array' })
      sheetNames.value = wb.SheetNames
      sheetHtmls.value = wb.SheetNames.map((name) => {
        const sheet = wb.Sheets[name]
        return XLSX.utils.sheet_to_html(sheet, { id: `sheet-${name}` })
      })
      return
    }
    if (k === 'docx') {
      const result = await mammoth.convertToHtml({ arrayBuffer: buf })
      docxHtml.value = result.value || `<p class="muted">${t('doc.emptyDoc')}</p>`
      return
    }
    if (k === 'pptx') {
      const zip = await JSZip.loadAsync(buf)
      const names = Object.keys(zip.files)
        .filter((n) => /^ppt\/slides\/slide\d+\.xml$/i.test(n))
        .sort((a, b) => {
          const na = Number(a.match(/slide(\d+)/i)?.[1] || 0)
          const nb = Number(b.match(/slide(\d+)/i)?.[1] || 0)
          return na - nb
        })
      const out: string[] = []
      for (const name of names) {
        const xml = await zip.files[name].async('string')
        const texts = [...xml.matchAll(/<a:t[^>]*>([^<]*)<\/a:t>/g)].map((m) => m[1])
        out.push(texts.join('\n').trim() || t('doc.noSlideText'))
      }
      slides.value = out.length ? out : [props.asset.text || t('doc.slideParseFail')]
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

watch(
  () => props.asset.id,
  () => {
    void load()
  },
  { immediate: true },
)
</script>

<style scoped>
.preview-pane {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preview-img {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  background: #f8f4eb;
}

.preview-frame {
  flex: 1;
  min-height: 520px;
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
}

.preview-pre {
  margin: 0;
  padding: 12px;
  background: #f8f4eb;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.88rem;
  max-height: 60vh;
  overflow: auto;
}

.preview-pre.slide {
  min-height: 200px;
}

.sheet-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.sheet-wrap {
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
}

.sheet-wrap :deep(table) {
  border-collapse: collapse;
  width: max-content;
  min-width: 100%;
  font-size: 0.82rem;
}

.sheet-wrap :deep(td),
.sheet-wrap :deep(th) {
  border: 1px solid var(--line);
  padding: 4px 8px;
}

.docx-html {
  padding: 12px 16px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 6px;
  overflow: auto;
  max-height: 70vh;
}

.docx-html :deep(p) {
  margin: 0 0 0.6em;
}

.pptx-nav {
  display: flex;
  align-items: center;
  gap: 10px;
}

.fallback {
  display: grid;
  gap: 10px;
  justify-items: start;
}
</style>
