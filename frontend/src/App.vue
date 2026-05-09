<template>
  <div class="min-h-screen bg-gray-950 font-sans">
    <nav class="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center gap-5">
      <span class="text-amber-400 font-mono font-bold text-lg cursor-default">个股评分</span>
      <router-link to="/" class="text-sm font-medium transition-colors" :class="isAStock ? 'text-white' : 'text-gray-400 hover:text-gray-200'">A股</router-link>
      <router-link to="/watchlist" class="text-sm font-medium transition-colors" :class="route.path === '/watchlist' ? 'text-white' : 'text-gray-400 hover:text-gray-200'">自选</router-link>
      <router-link to="/hk" class="text-sm font-medium transition-colors" :class="route.path === '/hk' ? 'text-white' : 'text-gray-500 hover:text-gray-300'">港美股</router-link>
      <div class="flex-1"></div>
      <div class="relative w-48">
        <input v-model="searchQuery" @keyup.enter="onSearch" @focus="searchFocused = true" @blur="onBlur"
          placeholder="搜索代码/名称..."
          class="w-full bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 pr-7 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-gray-500" />
        <span class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 text-xs">⌕</span>
        <div v-if="searchFocused && searchResults.length" class="absolute z-50 w-full mt-1 bg-gray-800 border border-gray-700 rounded-md shadow-lg overflow-hidden">
          <div v-for="s in searchResults" :key="s.code"
            @mousedown.prevent="goDetail(s.code)"
            class="flex items-center justify-between px-3 py-2 text-xs hover:bg-gray-700 cursor-pointer">
            <span class="text-white">{{ s.name }}</span>
            <span class="text-gray-500 font-mono">{{ s.code }}</span>
          </div>
        </div>
      </div>
      <span class="text-xs text-gray-500">{{ statusText }}</span>
      <button @click="doCollect" :disabled="collecting"
        class="bg-blue-800 hover:bg-blue-700 disabled:opacity-50 text-white text-xs px-3 py-1.5 rounded transition-colors">
        {{ collecting ? '同步中...' : '同步' }}
      </button>
    </nav>
    <router-view />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { triggerCollect, getCollectStatus, searchStocks } from './api'

const route = useRoute()
const router = useRouter()

const isAStock = computed(() => route.path === '/' || route.path === '/watchlist')

const collecting = ref(false)
const statusText = ref('')
let timer = null

const searchQuery = ref('')
const searchResults = ref([])
const searchFocused = ref(false)

async function onSearch() {
  const q = searchQuery.value.trim()
  if (!q) { searchResults.value = []; return }
  try { searchResults.value = await searchStocks(q) }
  catch { searchResults.value = [] }
}

function goDetail(code) {
  searchQuery.value = ''
  searchResults.value = []
  searchFocused.value = false
  router.push('/stock/' + code)
}

function onBlur() {
  setTimeout(() => { searchFocused.value = false }, 150)
}

async function doCollect() {
  collecting.value = true
  const market = route.path === '/hk' ? 'hk_us' : undefined
  await triggerCollect(market)
  poll()
}

async function poll() {
  const s = await getCollectStatus()
  const running = s.collect?.running || s.score?.running
  collecting.value = running
  const lastRun = s.collect?.last_run || s.score?.last_run
  if (lastRun) statusText.value = lastRun.slice(5, 16)
  if (running) timer = setTimeout(poll, 3000)
}

onMounted(poll)
onUnmounted(() => clearTimeout(timer))
</script>

<style>
body { font-family: 'Fira Sans', system-ui, -apple-system, sans-serif; }
.font-mono, table td, table th { font-family: 'Fira Code', ui-monospace, monospace; }
</style>
