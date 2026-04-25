<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-4">
      <div class="flex gap-4 border-b border-gray-800">
        <button
          v-for="t in tabs"
          :key="t.value"
          @click="tab = t.value"
          class="pb-2 text-sm font-medium border-b-2 transition-colors"
          :class="tab === t.value ? 'border-amber-400 text-amber-400' : 'border-transparent text-gray-500 hover:text-gray-300'"
        >{{ t.label }}</button>
      </div>
      <div class="flex items-center gap-3">
        <span v-if="dataDate" class="text-gray-500 text-sm font-mono">{{ dataDate }}</span>
        <button @click="showGuide = !showGuide"
          class="bg-gray-800 border rounded-md px-2.5 py-1 text-xs transition-colors"
          :class="showGuide ? 'border-blue-500 text-blue-400' : 'border-gray-700 text-gray-400 hover:text-gray-200'">
          ? 评分说明
        </button>
      </div>
    </div>
    <div v-if="showGuide" class="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-4">
      <h3 class="text-amber-400 text-sm font-bold mb-3">评分维度<span class="text-gray-600 font-normal ml-2 text-xs">各维度满分100，按策略权重加权得到总分</span></h3>
      <div class="grid grid-cols-5 gap-3 mb-4">
        <div v-for="d in dimensions" :key="d.key" class="bg-gray-950 rounded-lg p-3" :style="{ borderTop: `2px solid ${d.color}` }">
          <div class="font-bold text-xs" :style="{ color: d.color }">{{ d.label }}</div>
          <div class="text-gray-500 text-xs mt-1.5 leading-relaxed" v-html="d.desc"></div>
        </div>
      </div>
      <h3 class="text-amber-400 text-sm font-bold mb-3">评分策略</h3>
      <div class="grid grid-cols-3 gap-3">
        <div v-for="s in strategies" :key="s.name" class="bg-gray-950 rounded-lg p-3">
          <div class="font-bold text-xs" :style="{ color: s.color }">{{ s.label }}</div>
          <div class="text-gray-500 text-xs mt-1">{{ s.weight }}</div>
        </div>
      </div>
    </div>
    <!-- 搜索面板 -->
    <div v-if="tab === 'search'" class="mb-4">
      <div class="relative max-w-md">
        <input v-model="searchQuery" @keyup.enter="onSearch" placeholder="输入股票代码，按 Enter 搜索"
          class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-sm font-mono focus:outline-none focus:border-blue-500"
          :disabled="searchLoading" />
        <div v-if="searchLoading" class="absolute z-10 w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-sm text-gray-500 text-center">
          搜索中...
        </div>
        <div v-else-if="searchResults.length" class="absolute z-10 w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-lg overflow-hidden">
          <button v-for="s in searchResults" :key="s.code"
            @click="goDetail(s.code)"
            class="w-full flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-gray-700 transition-colors text-left">
            <span class="font-mono text-gray-300">{{ s.code }}</span>
            <span class="text-white">{{ s.name }}</span>
            <span class="ml-auto text-xs text-gray-500">{{ s.market }}</span>
          </button>
        </div>
        <div v-else-if="searchQuery && searchDone" class="absolute z-10 w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-sm text-gray-500 text-center">
          未找到匹配的股票
        </div>
      </div>
    </div>
    <!-- 行业板块 -->
    <div v-else-if="tab === 'industries'" class="space-y-2">
      <div v-if="!industries.length" class="text-gray-600 text-sm text-center py-8">加载中...</div>
      <div v-for="(item, idx) in industries" :key="item.name"
        class="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 flex items-center gap-4">
        <span class="text-gray-500 text-xs w-6 text-right">{{ idx + 1 }}</span>
        <span class="text-sm text-white font-medium w-24">{{ item.name }}</span>
        <span class="font-mono text-sm font-semibold" :class="item.change_pct > 0 ? 'text-red-400' : item.change_pct < 0 ? 'text-green-400' : 'text-gray-400'">
          {{ item.change_pct > 0 ? '+' : '' }}{{ item.change_pct.toFixed(2) }}%
        </span>
        <span class="text-xs text-gray-500">{{ item.count }}只</span>
        <span class="text-xs text-gray-500 ml-auto">
          领涨 <span class="text-gray-300">{{ item.leading_name }}</span>
          <span class="font-mono ml-1" :class="item.leading_pct > 0 ? 'text-red-400' : 'text-green-400'">{{ item.leading_pct > 0 ? '+' : '' }}{{ item.leading_pct.toFixed(2) }}%</span>
        </span>
      </div>
    </div>
    <ScoreTable v-else-if="tab !== 'search'" :rows="rows" :tab="tab" @added="load" />
  </div>
</template>

<script setup>
import { ref, shallowRef, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ScoreTable from '../components/ScoreTable.vue'
import { getLeaderboard, searchStocks, getIndustries } from '../api'

const tab = ref('other')
const rows = shallowRef([])
const dataDate = ref('')
const showGuide = ref(false)
const router = useRouter()

const searchQuery = ref('')
const searchResults = ref([])
const searchLoading = ref(false)
const searchDone = ref(false)
const industries = ref([])

const tabs = [
  { value: 'other', label: '热门' },
  { value: 'watchlist', label: '自选股' },
  { value: 'industries', label: '行业' },
  { value: 'search', label: '搜索' },
]

const dimensions = [
  { key: 'technical', label: '技术面', color: '#60a5fa', desc: 'MA趋势 30分<br>MACD 25分<br>RSI 20分<br>KDJ 15分<br>BOLL 10分' },
  { key: 'capital', label: '资金面', color: '#f59e0b', desc: '主力净流入<br>超大单净流入<br>北向资金<br>融资净买入' },
  { key: 'fundamental', label: '基本面', color: '#34d399', desc: 'PE市盈率<br>PB市净率<br>ROE<br>净利润增速' },
  { key: 'news', label: '消息面', color: '#a78bfa', desc: '新闻情绪评分<br>公告类型<br>研报评级' },
  { key: 'heat', label: '市场热度', color: '#fb923c', desc: '涨跌幅<br>换手率<br>量比<br>连板天数' },
]

const strategies = [
  { name: 'short_term', label: '短线策略', color: '#f59e0b', weight: '技术35% · 资金25% · 热度30% · 消息10%' },
  { name: 'trend', label: '趋势策略', color: '#60a5fa', weight: '技术40% · 资金30% · 热度20% · 消息5% · 基本面5%' },
  { name: 'value', label: '价值策略', color: '#34d399', weight: '基本面50% · 技术20% · 资金15% · 消息10% · 热度5%' },
]

async function load() {
  if (tab.value === 'search') return
  if (tab.value === 'industries') {
    if (!industries.value.length) industries.value = await getIndustries()
    return
  }
  const res = await getLeaderboard(tab.value)
  dataDate.value = res.date || ''
  rows.value = res.stocks || res || []
}

async function onSearch() {
  const q = searchQuery.value.trim()
  if (!q) { searchResults.value = []; searchDone.value = false; return }
  searchLoading.value = true
  searchDone.value = false
  try {
    searchResults.value = await searchStocks(q)
  } catch { searchResults.value = [] }
  searchLoading.value = false
  searchDone.value = true
}

function goDetail(code) {
  searchQuery.value = ''
  searchResults.value = []
  searchDone.value = false
  router.push('/stock/' + code)
}

watch(tab, load)
onMounted(load)
</script>
