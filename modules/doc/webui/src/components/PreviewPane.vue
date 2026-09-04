<template>
  <div class="preview-wrap">
    <div class="preview-pane" :class="{ filled: kind === 'xlsx' || kind === 'docx' || kind === 'text' || kind === 'pptx' }">
      <p
        v-if="asset.text_status === 'pending' || asset.text_status === 'running'"
        class="extract-banner"
      >{{ t('doc.extracting') }}</p>
      <p v-else-if="asset.text_status === 'failed'" class="extract-banner fail">
        {{ t('doc.extractFailed') }}<span v-if="asset.text_error"> — {{ asset.text_error }}</span>
      </p>

      <ExcelPreview v-if="kind === 'xlsx'" :asset-id="asset.id" />

      <p v-else-if="loading" class="muted">{{ t('doc.previewLoading') }}</p>
      <p v-else-if="error" class="error">{{ error }}</p>

      <template v-else-if="kind === 'pdf' || kind === 'html'">
        <iframe class="preview-frame" :src="contentSrc" title="preview" />
      </template>

      <template v-else-if="kind === 'image'">
        <img class="preview-img" :src="contentSrc" :alt="asset.filename" />
      </template>

      <template v-else-if="kind === 'text'">
        <pre class="preview-pre">{{ textBody }}</pre>
      </template>

      <template v-else-if="kind === 'docx'">
        <div class="docx-html" v-html="docxHtml" />
      </template>

      <template v-else-if="kind === 'pptx'">
        <div class="pptx-nav">
          <button type="button" class="btn"
           :disabled="slideIndex <= 0"
           :title="t('doc.prevSlide')"
           @click="slideIndex--">
            {{ t('doc.prevSlide') }}
          </button>
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

    <button
      type="button"
      class="extract-fab"
      :aria-label="t('doc.viewExtract')"
      :title="t('doc.viewExtract')"
      @click="openExtract"
    >
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
        <path
          fill="currentColor"
          d="M6 3h8l4 4v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zm7 1.5V8h3.5L13 4.5zM8 11h8v1.5H8V11zm0 3h8v1.5H8V14zm0 3h5v1.5H8V17z"
        />
      </svg>
    </button>

    <div
      v-if="showExtract"
      class="extract-overlay"
      role="dialog"
      aria-modal="true"
      :aria-label="t('doc.extractTitle')"
    >
      <header class="extract-overlay-head">
        <strong>{{ t('doc.extractTitle') }}</strong>
        <button type="button" class="dialog-close" :aria-label="t('doc.close')" @click="showExtract = false">×</button>
      </header>
      <p v-if="extractLoading" class="muted extract-overlay-body">{{ t('doc.loading') }}</p>
      <pre v-else class="extract-overlay-body">{{ extractText || t('doc.extractEmpty') }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import mammoth from 'mammoth'
import JSZip from 'jszip'
import {
  contentUrl,
  fetchContentBlob,
  getAsset,
  type DocAsset,
} from '../api/doc'
import { useI18n } from '@modoor/hooks'
import ExcelPreview from './ExcelPreview.vue'

const props = defineProps<{ asset: DocAsset }>()
const { t } = useI18n()

const loading = ref(false)
const error = ref('')
const textBody = ref('')
const docxHtml = ref('')
const slides = ref<string[]>([])
const slideIndex = ref(0)
const showExtract = ref(false)
const extractText = ref('')
const extractLoading = ref(false)

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

async function openExtract() {
  showExtract.value = true
  extractLoading.value = true
  extractText.value = props.asset.text || ''
  try {
    const res = await getAsset(props.asset.id, { full: true })
    extractText.value = res.asset.text || ''
  } catch (e) {
    if (!extractText.value) {
      extractText.value = e instanceof Error ? e.message : String(e)
    }
  } finally {
    extractLoading.value = false
  }
}

function onExtractKey(ev: KeyboardEvent) {
  if (ev.key === 'Escape' && showExtract.value) {
    showExtract.value = false
  }
}

async function load() {
  if (kind.value === 'xlsx') return
  loading.value = true
  error.value = ''
  textBody.value = ''
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
    showExtract.value = false
    extractText.value = ''
    void load()
  },
  { immediate: true },
)

watch(
  () => props.asset.text,
  (text) => {
    if (showExtract.value && text) extractText.value = text
  },
)

onMounted(() => window.addEventListener('keydown', onExtractKey))
onUnmounted(() => window.removeEventListener('keydown', onExtractKey))
</script>

<style scoped>
.preview-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.preview-pane {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preview-pane.filled {
  overflow: hidden;
}

.extract-fab {
  position: absolute;
  right: 14px;
  bottom: 14px;
  z-index: 6;
  width: 36px;
  height: 36px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: #fff;
  color: #1f2937;
  display: grid;
  place-items: center;
  cursor: pointer;
  box-shadow: 0 4px 14px #00000022;
}

.extract-fab:hover {
  background: #f8f4eb;
}

.extract-overlay {
  position: absolute;
  inset: 8px;
  z-index: 8;
  display: flex;
  flex-direction: column;
  background: #fffdf8;
  border: 1px solid var(--line);
  border-radius: 10px;
  box-shadow: 0 10px 40px #00000033;
  overflow: hidden;
}

.extract-overlay-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
}

.extract-overlay-body {
  margin: 0;
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 12px 14px;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.86rem;
}

.dialog-close {
  border: 0;
  background: transparent;
  font-size: 1.2rem;
  line-height: 1;
  cursor: pointer;
  color: inherit;
}

.extract-banner {
  margin: 0;
  font-size: 0.82rem;
  padding: 6px 10px;
  border-radius: 6px;
  background: #f5e0c4;
  color: #9a5b12;
}

.extract-banner.fail {
  background: #f3d2d2;
  color: #8b1e1e;
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
  flex: 1;
  min-height: 0;
  margin: 0;
  padding: 12px;
  background: #f8f4eb;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.88rem;
  overflow: auto;
}

.preview-pre.slide {
  min-height: 0;
}

.docx-html {
  flex: 1;
  min-height: 0;
  padding: 12px 16px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 6px;
  overflow: auto;
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
