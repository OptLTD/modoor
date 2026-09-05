<template>
  <div class="page">
    <header class="head">
      <h1>Transport / TMS</h1>
      <p class="meta">表前缀 <code>tms_</code></p>
    </header>
    <p v-if="error" class="err">{{ error }}</p>
    <ul v-if="items.length" class="list">
      <li v-for="s in items" :key="s.id">
        <strong>{{ s.ref_no }}</strong>
        · {{ s.origin }} → {{ s.destination }}
        · {{ s.status }}
      </li>
    </ul>
    <p v-else class="meta">暂无运单</p>
    <form class="form" @submit.prevent="onAdd">
      <input v-model="refNo" placeholder="运单号" required />
      <input v-model="origin" placeholder="起点" required />
      <input v-model="destination" placeholder="终点" required />
      <button type="submit" :disabled="saving">创建</button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { addShipment, listShipments, type Shipment } from '../api/transport'

const items = ref<Shipment[]>([])
const refNo = ref('')
const origin = ref('')
const destination = ref('')
const error = ref('')
const saving = ref(false)

async function reload() {
  const data = await listShipments()
  items.value = data.items
}

async function onAdd() {
  error.value = ''
  saving.value = true
  try {
    await addShipment({
      ref_no: refNo.value,
      origin: origin.value,
      destination: destination.value,
    })
    refNo.value = ''
    origin.value = ''
    destination.value = ''
    await reload()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  reload().catch((e) => {
    error.value = e instanceof Error ? e.message : String(e)
  })
})
</script>

<style scoped>
.page { padding: 0.25rem 0 1.5rem; }
.head { margin-bottom: 1rem; }
h1 { margin: 0 0 0.25rem; font-size: 1.35rem; }
.meta { color: var(--muted, #78716c); font-size: 0.9rem; margin: 0; }
.err { color: #b91c1c; }
.list { padding-left: 1.2rem; }
.form {
  display: flex;
  gap: 0.5rem;
  margin-top: 1rem;
  flex-wrap: wrap;
}
input {
  flex: 1;
  min-width: 7rem;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--line, #e7e5e4);
  font: inherit;
  background: #fff;
}
button {
  font: inherit;
  padding: 0.45rem 0.85rem;
  border: none;
  background: var(--accent, #0f766e);
  color: #fff;
  cursor: pointer;
}
button:disabled { opacity: 0.6; cursor: default; }
</style>
