<template>
  <div class="min-h-screen bg-gray-950 font-sans">
    <nav class="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center gap-6">
      <span class="text-amber-400 font-mono font-bold text-lg cursor-default">A股评分系统</span>
      <router-link to="/" class="text-gray-300 hover:text-white transition-colors">排行榜</router-link>
      <router-link to="/history" class="text-gray-300 hover:text-white transition-colors">历史趋势</router-link>
      <div class="ml-auto flex items-center gap-3">
        <span class="text-xs text-gray-500">{{ statusText }}</span>
        <button
          @click="doCollect"
          :disabled="collecting"
          class="bg-blue-800 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-3 py-1 rounded transition-colors"
        >
          {{ collecting ? '同步中...' : '同步' }}
        </button>
      </div>
    </nav>
    <router-view />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { triggerCollect, getCollectStatus } from './api'

const collecting = ref(false)
const statusText = ref('')
let timer = null

async function doCollect() {
  collecting.value = true
  await triggerCollect()
  poll()
}

async function poll() {
  const s = await getCollectStatus()
  collecting.value = s.running
  if (s.last_run) statusText.value = '上次: ' + s.last_run.slice(0, 16)
  if (s.running) timer = setTimeout(poll, 3000)
}

onMounted(poll)
onUnmounted(() => clearTimeout(timer))
</script>

<style>
body { font-family: 'Fira Sans', system-ui, -apple-system, sans-serif; }
.font-mono, table td, table th { font-family: 'Fira Code', ui-monospace, monospace; }
</style>
