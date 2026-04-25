<template>
  <div class="p-6 max-w-5xl mx-auto">
    <button @click="$router.back()" class="text-gray-400 hover:text-white mb-4 text-sm">← 返回</button>
    <div v-if="!data" class="space-y-4 py-6">
      <div class="flex items-center gap-4">
        <div class="h-8 w-40 rounded bg-gray-800 animate-pulse"></div>
        <div class="h-5 w-20 rounded bg-gray-800 animate-pulse"></div>
      </div>
      <div class="h-28 rounded-lg bg-gray-800 animate-pulse"></div>
      <div class="h-20 rounded-lg bg-gray-800 animate-pulse"></div>
      <div class="h-20 rounded-lg bg-gray-800 animate-pulse"></div>
    </div>
    <template v-else-if="data?.error && !collectLoading">
      <div class="text-center py-16">
        <p class="text-gray-400 mb-2">该股票暂无评分数据</p>
      </div>
    </template>
    <template v-else-if="collectLoading">
      <div class="text-center py-16">
        <p class="text-gray-400 animate-pulse">正在采集数据并评分，请稍候...</p>
      </div>
    </template>
    <template v-else>
      <div class="flex items-center gap-4 mb-6">
        <h1 class="text-2xl font-bold">{{ data.name }}</h1>
        <span class="font-mono text-gray-400">{{ data.code }}</span>
        <div class="ml-auto flex items-center gap-3">
          <button v-if="isWatchlist" @click="removeWatch" class="text-xs border border-gray-600 text-gray-400 px-3 py-1 rounded hover:text-red-400 hover:border-red-400 transition-colors">已加自选</button>
          <button v-else @click="addWatch" class="text-xs border border-amber-600 text-amber-400 px-3 py-1 rounded hover:bg-amber-900/30 transition-colors">+ 自选</button>
          <span v-if="data.short_term" class="bg-amber-900/40 text-amber-300 border border-amber-800/40 px-3 py-1 rounded-full font-mono font-bold text-lg">
            短线 {{ data.short_term.total }} 分
          </span>
          <span v-if="data.trend" class="bg-blue-900/40 text-blue-300 border border-blue-800/40 px-3 py-1 rounded-full font-mono font-bold text-lg">
            趋势 {{ data.trend.total }} 分
          </span>
        </div>
      </div>

      <!-- 公司概况 -->
      <section class="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <h2 class="text-sm text-gray-400 font-semibold mb-3">公司概况</h2>
        <div v-if="profile" class="space-y-3">
          <div class="flex flex-wrap gap-2">
            <span v-if="profile.industry" class="bg-blue-900/40 text-blue-300 text-xs px-2 py-0.5 rounded">
              {{ profile.industry }}
            </span>
            <span v-for="c in profile.concepts" :key="c" class="bg-gray-800 text-xs px-2 py-0.5 rounded text-gray-300">
              {{ c }}
            </span>
          </div>
          <div v-if="profile.business" class="text-sm text-gray-200 leading-relaxed">
            <span :class="{ 'line-clamp-2': !showFullBiz }">{{ profile.business }}</span>
            <button v-if="profile.business.length > 80"
              @click="showFullBiz = !showFullBiz"
              class="ml-2 text-blue-400 text-xs">{{ showFullBiz ? '收起' : '展开' }}</button>
          </div>
          <div class="text-xs text-gray-500 flex gap-4 flex-wrap">
            <span v-if="profile.list_date">上市：{{ profile.list_date }}</span>
            <span v-if="profile.total_mv">总市值：{{ profile.total_mv }} 亿</span>
            <span v-if="profile.float_mv">流通市值：{{ profile.float_mv }} 亿</span>
            <span v-if="profile.total_share">总股本：{{ profile.total_share }} 亿</span>
            <span v-if="profile.float_share">流通股本：{{ profile.float_share }} 亿</span>
            <span v-if="profile.pe">PE：{{ profile.pe }}</span>
            <span v-if="profile.pb">PB：{{ profile.pb }}</span>
          </div>
        </div>
        <div v-else class="text-gray-600 text-xs py-2">暂无公司资料</div>
      </section>

      <!-- 板块关联 -->
      <section class="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <h2 class="text-sm text-gray-400 font-semibold mb-3">板块关联</h2>
        <div v-if="profile?.industry && trendInfo" class="flex flex-wrap items-center gap-4 text-sm">
          <span class="text-gray-200">{{ profile.industry }}</span>
          <span>今日 <span :class="pctColor(trendInfo.industry_change)" class="font-mono">{{ fmtPct(trendInfo.industry_change) }}</span></span>
          <span>近5日 <span :class="pctColor(trendInfo.industry_change_5d)" class="font-mono">{{ fmtPct(trendInfo.industry_change_5d) }}</span></span>
          <span>近20日 <span :class="pctColor(trendInfo.industry_change_20d)" class="font-mono">{{ fmtPct(trendInfo.industry_change_20d) }}</span></span>
        </div>
        <div v-else class="text-gray-600 text-xs py-2">暂无板块数据</div>
      </section>

      <!-- 近期趋势 -->
      <section class="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <h2 class="text-sm text-gray-400 font-semibold mb-3">近期趋势</h2>
        <div v-if="trendInfo" class="space-y-3">
          <div class="flex flex-wrap gap-6 text-sm">
            <span>近5日 <span :class="pctColor(trendInfo.return_5d)" class="font-mono font-semibold">{{ fmtPct(trendInfo.return_5d) }}</span></span>
            <span>近20日 <span :class="pctColor(trendInfo.return_20d)" class="font-mono font-semibold">{{ fmtPct(trendInfo.return_20d) }}</span></span>
            <span>近60日 <span :class="pctColor(trendInfo.return_60d)" class="font-mono font-semibold">{{ fmtPct(trendInfo.return_60d) }}</span></span>
          </div>
          <div v-if="trendInfo.pattern_tags?.length" class="flex flex-wrap gap-2">
            <span v-for="t in trendInfo.pattern_tags" :key="t"
              class="bg-amber-900/30 text-amber-300 text-xs px-2 py-0.5 rounded border border-amber-800/30">
              {{ t }}
            </span>
          </div>
        </div>
        <div v-else class="text-gray-600 text-xs py-2">暂无近期趋势数据</div>
      </section>

      <!-- AI 综合研判 -->
      <section class="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm text-gray-400 font-semibold">AI 综合研判</span>
          <button @click="fetchAnalysis" :disabled="aiLoading"
            class="px-3 py-1 rounded text-xs transition-colors"
            :class="aiLoading ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-blue-800 text-white hover:bg-blue-700'"
          >{{ aiLoading ? '分析中...' : (data.ai_analysis ? '重新分析' : '开始分析') }}</button>
        </div>
        <div v-if="aiLoading" class="text-gray-500 text-center py-4 text-xs">AI 正在分析中...</div>
        <div v-else-if="aiError" class="text-red-400 text-xs py-1">{{ aiError }}</div>
        <div v-else-if="displayAnalysis" class="ai-analysis text-gray-200 text-sm leading-relaxed" v-html="displayAnalysis"></div>
        <div v-else class="text-gray-600 text-center py-4 text-xs">点击"开始分析"获取 AI 综合研判</div>
      </section>

      <!-- 雷达图 + 五维评分 -->
      <div class="flex gap-6 flex-wrap mb-4">
        <RadarChart :scores="data.scores" />
        <div class="flex-1 grid grid-cols-1 gap-3 min-w-[260px]">
          <div v-for="dim in dimensions" :key="dim.key"
            class="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 flex items-center justify-between">
            <span class="text-gray-400 text-sm">{{ dim.label }}</span>
            <span class="font-mono font-semibold text-lg" :class="scoreColor(data.scores?.[dim.key])">
              {{ data.scores?.[dim.key] ?? '-' }}
            </span>
          </div>
        </div>
      </div>

      <!-- K线图 -->
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <h2 class="text-sm text-gray-400 mb-3 font-semibold">K线图 · TradingView</h2>
        <TradingViewChart :code="route.params.code" />
      </div>

      <!-- 原始指标（默认折叠） -->
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <button @click="showRaw = !showRaw" class="w-full flex items-center justify-between text-sm text-gray-400 font-semibold">
          <span>原始指标数据</span>
          <span class="text-xs">{{ showRaw ? '收起 ▲' : '展开 ▼' }}</span>
        </button>
        <div v-if="showRaw" class="grid grid-cols-3 gap-2 text-xs font-mono mt-3">
          <div v-for="(val, key) in displayRaw" :key="key" class="flex justify-between border-b border-gray-800/50 py-1">
            <span class="text-gray-500">{{ key }}</span>
            <span class="text-gray-200">{{ val ?? '-' }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import RadarChart from '../components/RadarChart.vue'
import TradingViewChart from '../components/TradingViewChart.vue'
import { getStockDetail, getStockProfile, getAnalysis, addWatchlist, removeWatchlist, checkWatchlist, collectSingle } from '../api'

function preprocessBold(text) {
  return text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
}

const route = useRoute()
const data = ref(null)
const profile = ref(null)
const aiResult = ref('')
const aiLoading = ref(false)
const aiError = ref('')
const showFullBiz = ref(false)
const showRaw = ref(false)
const isWatchlist = ref(false)
const collectLoading = ref(false)

const trendInfo = computed(() => data.value?.trend_info || null)
const displayAnalysis = computed(() => {
  const text = aiResult.value || data.value?.ai_analysis || ''
  return text ? marked.parse(preprocessBold(text)) : ''
})

const dimensions = [
  { key: 'technical', label: '技术面' },
  { key: 'capital', label: '资金面' },
  { key: 'fundamental', label: '基本面' },
  { key: 'news', label: '消息面' },
  { key: 'heat', label: '市场热度' },
]
const SKIP = new Set(['code', 'date', '_sa_instance_state', 'ai_analysis',
  'return_5d', 'return_20d', 'return_60d',
  'industry_change', 'industry_change_5d', 'industry_change_20d', 'pattern_tags'])
const displayRaw = computed(() => {
  if (!data.value?.raw) return {}
  return Object.fromEntries(
    Object.entries(data.value.raw).filter(([k, v]) => !SKIP.has(k) && v != null)
  )
})

function scoreColor(s) {
  if (!s) return 'text-gray-400'
  if (s >= 75) return 'text-green-400'
  if (s >= 50) return 'text-yellow-400'
  return 'text-red-400'
}
function pctColor(v) {
  if (v === null || v === undefined) return 'text-gray-500'
  return v > 0 ? 'text-red-400' : (v < 0 ? 'text-green-400' : 'text-gray-300')
}
function fmtPct(v) {
  if (v === null || v === undefined) return '-'
  const sign = v > 0 ? '+' : ''
  return `${sign}${v.toFixed(2)}%`
}

async function load() {
  const code = route.params.code
  const [detail, prof, watched] = await Promise.allSettled([
    getStockDetail(code),
    getStockProfile(code),
    checkWatchlist(code),
  ])
  if (detail.status === 'fulfilled') data.value = detail.value
  if (prof.status === 'fulfilled') profile.value = prof.value
  if (watched.status === 'fulfilled') isWatchlist.value = watched.value
  aiResult.value = ''
  aiError.value = ''
  // No score data → trigger single stock collection then reload
  if (data.value?.error) {
    collectLoading.value = true
    await collectSingle(code)
    const redetail = await getStockDetail(code).catch(() => null)
    if (redetail) data.value = redetail
    collectLoading.value = false
  }
}
async function addWatch() {
  await addWatchlist(route.params.code, data.value?.name || '')
  isWatchlist.value = true
}
async function removeWatch() {
  await removeWatchlist(route.params.code)
  isWatchlist.value = false
}
async function fetchAnalysis() {
  aiError.value = ''
  aiLoading.value = true
  try {
    const res = await getAnalysis(route.params.code)
    aiResult.value = res.analysis
  } catch (e) {
    aiError.value = e.response?.data?.detail || 'AI 分析请求失败'
  }
  aiLoading.value = false
}
onMounted(load)
</script>

<style scoped>
.ai-analysis :deep(p) { margin: 0.4em 0; }
.ai-analysis :deep(ul), .ai-analysis :deep(ol) { margin: 0.4em 0; padding-left: 1.5em; }
.ai-analysis :deep(li) { margin: 0.2em 0; }
.ai-analysis :deep(strong) { color: #93c5fd; font-weight: 600; }
.ai-analysis :deep(h1), .ai-analysis :deep(h2), .ai-analysis :deep(h3) {
  color: #e5e7eb; font-weight: 700; margin: 0.6em 0 0.3em; font-size: 0.95rem;
}
.line-clamp-2 {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
</style>
