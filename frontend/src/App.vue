<template>
  <div class="min-h-screen font-sans relative">
    <!-- Nav -->
    <nav class="glass-nav sticky top-0 z-50 px-5 py-0 flex items-center h-14">
      <!-- Logo -->
      <router-link to="/" class="flex items-center gap-2.5 mr-6 shrink-0 group">
        <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/20 group-hover:shadow-amber-500/30 transition-shadow">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 10L5 4L8 8L12 2" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </div>
        <span class="text-[15px] font-semibold tracking-tight text-white/90">个股评分</span>
      </router-link>

      <!-- Market tabs -->
      <div class="flex items-center gap-0.5 mr-4">
        <router-link to="/"
          class="nav-tab" :class="isAStock ? 'nav-tab-active' : 'nav-tab-inactive'">A股</router-link>
        <router-link to="/watchlist"
          class="nav-tab" :class="route.path === '/watchlist' ? 'nav-tab-active' : 'nav-tab-inactive'">自选</router-link>
        <router-link to="/hk"
          class="nav-tab" :class="route.path === '/hk' ? 'nav-tab-active' : 'nav-tab-inactive'">港美股</router-link>
        <router-link to="/etf"
          class="nav-tab" :class="route.path === '/etf' ? 'nav-tab-active' : 'nav-tab-inactive'">ETF</router-link>
      </div>

      <div class="flex-1"></div>

      <!-- Search -->
      <div class="relative w-52 mr-4">
        <div class="search-input-wrapper" :class="{ focused: searchFocused }">
          <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
          <input v-model="searchQuery" @keyup.enter="onSearch" @focus="searchFocused = true" @blur="onBlur"
            placeholder="搜索代码 / 名称..."
            class="search-input" />
          <kbd v-if="!searchQuery" class="search-kbd">/</kbd>
        </div>
        <!-- Dropdown -->
        <Transition name="dropdown">
          <div v-if="searchFocused && searchResults.length" class="search-dropdown">
            <div v-for="s in searchResults" :key="s.code"
              @mousedown.prevent="goDetail(s.code)"
              class="search-result-item">
              <span class="text-white/90 text-sm">{{ s.name }}</span>
              <span class="text-white/30 text-xs font-mono">{{ s.code }}</span>
            </div>
          </div>
        </Transition>
      </div>

      <!-- Status -->
      <div v-if="statusText" class="status-pill mr-3">
        <span class="status-dot"></span>
        <span>{{ statusText }}</span>
      </div>

      <!-- Sync button -->
      <button @click="doCollect" :disabled="collecting"
        class="sync-btn" :class="{ syncing: collecting }">
        <svg v-if="collecting" class="animate-spin w-3.5 h-3.5" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" stroke-dasharray="32" stroke-linecap="round"/></svg>
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.3"/></svg>
        <span>{{ collecting ? '同步中' : '同步' }}</span>
      </button>
    </nav>

    <!-- Page Content -->
    <main class="relative z-10">
      <router-view />
    </main>
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
  const market = route.path === '/hk' ? 'hk_us' : (route.path === '/etf' ? 'etf' : undefined)
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
/* ── Nav glass ─────────────────────────────────── */
.glass-nav {
  background: rgba(10, 14, 26, 0.75);
  backdrop-filter: blur(20px) saturate(1.2);
  -webkit-backdrop-filter: blur(20px) saturate(1.2);
  border-bottom: 1px solid rgba(148, 163, 184, 0.07);
}

/* ── Nav tabs ──────────────────────────────────── */
.nav-tab {
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  transition: all 150ms cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
}
.nav-tab-active {
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
}
.nav-tab-inactive {
  color: rgba(148, 163, 184, 0.7);
}
.nav-tab-inactive:hover {
  color: rgba(241, 245, 249, 0.8);
  background: rgba(148, 163, 184, 0.05);
}

/* ── Search ────────────────────────────────────── */
.search-input-wrapper {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(148, 163, 184, 0.06);
  border: 1px solid rgba(148, 163, 184, 0.08);
  border-radius: 8px;
  padding: 0 10px;
  height: 32px;
  transition: all 200ms cubic-bezier(0.16, 1, 0.3, 1);
}
.search-input-wrapper.focused {
  background: rgba(148, 163, 184, 0.1);
  border-color: rgba(245, 158, 11, 0.3);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.06);
}
.search-icon {
  color: rgba(148, 163, 184, 0.4);
  flex-shrink: 0;
  transition: color 200ms;
}
.search-input-wrapper.focused .search-icon {
  color: rgba(245, 158, 11, 0.6);
}
.search-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  font-size: 12px;
  color: #f1f5f9;
  font-family: 'DM Sans', sans-serif;
}
.search-input::placeholder {
  color: rgba(148, 163, 184, 0.35);
}
.search-kbd {
  font-family: 'DM Sans', sans-serif;
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(148, 163, 184, 0.08);
  border: 1px solid rgba(148, 163, 184, 0.1);
  color: rgba(148, 163, 184, 0.3);
  flex-shrink: 0;
}

/* ── Search dropdown ───────────────────────────── */
.search-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  background: rgba(17, 24, 39, 0.95);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
  padding: 4px;
}
.search-result-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 120ms;
}
.search-result-item:hover {
  background: rgba(245, 158, 11, 0.08);
}

/* ── Dropdown transition ───────────────────────── */
.dropdown-enter-active { transition: all 200ms cubic-bezier(0.16, 1, 0.3, 1); }
.dropdown-leave-active { transition: all 150ms ease-in; }
.dropdown-enter-from, .dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
}

/* ── Status pill ───────────────────────────────── */
.status-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: rgba(148, 163, 184, 0.5);
  font-variant-numeric: tabular-nums;
}
.status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: rgba(34, 197, 94, 0.6);
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.3);
}

/* ── Sync button ───────────────────────────────── */
.sync-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 14px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  font-family: 'DM Sans', sans-serif;
  background: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(59, 130, 246, 0.2);
  color: rgba(96, 165, 250, 0.9);
  cursor: pointer;
  transition: all 200ms cubic-bezier(0.16, 1, 0.3, 1);
}
.sync-btn:hover:not(:disabled) {
  background: rgba(59, 130, 246, 0.2);
  border-color: rgba(59, 130, 246, 0.35);
  color: #93bbfd;
}
.sync-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.sync-btn.syncing {
  background: rgba(59, 130, 246, 0.08);
}
</style>
