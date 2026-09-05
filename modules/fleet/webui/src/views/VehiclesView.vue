<template>
  <div class="page">
    <header class="head">
      <h1>Fleet / VMS</h1>
      <p class="meta">表前缀 <code>vms_</code></p>
    </header>
    <p v-if="error" class="err">{{ error }}</p>
    <ul v-if="items.length" class="list">
      <li v-for="v in items" :key="v.id">
        <strong>{{ v.plate_no }}</strong>
        <span v-if="v.model"> · {{ v.model }}</span>
        · {{ v.status }}
      </li>
    </ul>
    <p v-else class="meta">暂无车辆</p>
    <form class="form" @submit.prevent="onAdd">
      <input v-model="plateNo" placeholder="车牌" required />
      <input v-model="model" placeholder="车型（可选）" />
      <button type="submit" :disabled="saving">登记</button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { addVehicle, listVehicles, type Vehicle } from '../api/fleet'

const items = ref<Vehicle[]>([])
const plateNo = ref('')
const model = ref('')
const error = ref('')
const saving = ref(false)

async function reload() {
  const data = await listVehicles()
  items.value = data.items
}

async function onAdd() {
  error.value = ''
  saving.value = true
  try {
    await addVehicle({ plate_no: plateNo.value, model: model.value || undefined })
    plateNo.value = ''
    model.value = ''
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
  min-width: 8rem;
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
