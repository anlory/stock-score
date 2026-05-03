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
          <a :href="`https://stockpage.10jqka.com.cn/${data.code}/`" target="_blank" class="text-xs text-blue-400 hover:text-blue-300">同花顺 ↗</a>
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
          <!-- 简介 -->
          <div v-if="profile.introduction" class="text-sm text-gray-300 leading-relaxed">
            <span :class="{ 'line-clamp-3': !showFullBiz }">{{ profile.introduction }}</span>
            <button v-if="profile.introduction.length > 80"
              @click="showFullBiz = !showFullBiz"
              class="ml-2 text-blue-400 text-xs">{{ showFullBiz ? '收起' : '展开' }}</button>
          </div>
          <!-- 主营 -->
          <div v-if="profile.main_business" class="text-xs text-gray-400">
            <span class="text-gray-500">主营：</span>{{ profile.main_business }}
          </div>
          <!-- 行业 + 概念 -->
          <div class="flex flex-wrap gap-1.5">
            <span v-if="profile.industry" class="bg-blue-900/40 text-blue-300 text-xs px-2 py-0.5 rounded">{{ profile.industry }}</span>
            <span v-for="c in profile.concepts" :key="c" class="bg-gray-800 text-xs px-2 py-0.5 rounded text-gray-300">{{ c }}</span>
          </div>
          <!-- 信息网格 -->
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-1.5 text-xs">
            <div v-if="profile.chairman"><span class="text-gray-500">董事长</span> <span class="text-gray-200 ml-1">{{ profile.chairman }}</span></div>
            <div v-if="profile.manager"><span class="text-gray-500">总经理</span> <span class="text-gray-200 ml-1">{{ profile.manager }}</span></div>
            <div v-if="profile.setup_date"><span class="text-gray-500">成立</span> <span class="text-gray-200 ml-1">{{ profile.setup_date }}</span></div>
            <div v-if="profile.list_date"><span class="text-gray-500">上市</span> <span class="text-gray-200 ml-1">{{ profile.list_date }}</span></div>
            <div v-if="profile.province || profile.city"><span class="text-gray-500">地区</span> <span class="text-gray-200 ml-1">{{ [profile.province, profile.city].filter(Boolean).join(' ') }}</span></div>
            <div v-if="profile.employees"><span class="text-gray-500">员工</span> <span class="text-gray-200 ml-1">{{ Math.round(profile.employees).toLocaleString() }}</span></div>
            <div v-if="profile.total_mv"><span class="text-gray-500">总市值</span> <span class="text-gray-200 ml-1">{{ Math.round(profile.total_mv) }} 亿</span></div>
            <div v-if="profile.float_mv"><span class="text-gray-500">流通市值</span> <span class="text-gray-200 ml-1">{{ Math.round(profile.float_mv) }} 亿</span></div>
            <div v-if="profile.total_share"><span class="text-gray-500">总股本</span> <span class="text-gray-200 ml-1">{{ profile.total_share }} 亿</span></div>
            <div v-if="profile.float_share"><span class="text-gray-500">流通股</span> <span class="text-gray-200 ml-1">{{ profile.float_share }} 亿</span></div>
            <div v-if="profile.pe"><span class="text-gray-500">PE</span> <span class="text-gray-200 ml-1">{{ Math.round(profile.pe) }}</span></div>
            <div v-if="profile.pb"><span class="text-gray-500">PB</span> <span class="text-gray-200 ml-1">{{ Math.round(profile.pb * 100) / 100 }}</span></div>
          </div>
          <!-- 办公地址 -->
          <div v-if="profile.office" class="text-xs text-gray-500">
            <span>地址：</span><span class="text-gray-400">{{ profile.office }}</span>
          </div>
          <!-- 经营范围 -->
          <div v-if="profile.business" class="text-xs text-gray-500">
            <span>经营范围：</span><span class="text-gray-400">{{ profile.business }}</span>
          </div>
        </div>
        <div v-else class="text-gray-600 text-xs py-2">暂无公司资料</div>
      </section>

      <!-- 板块关联 -->
      <section class="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <h2 class="text-sm text-gray-400 font-semibold mb-3">板块关联</h2>
        <div v-if="profile?.industry" class="flex flex-wrap items-center gap-2 text-sm">
          <span class="bg-blue-900/40 text-blue-300 text-xs px-2 py-0.5 rounded">{{ profile.industry }}</span>
          <span v-for="c in profile.concepts" :key="c" class="bg-gray-800 text-xs px-2 py-0.5 rounded text-gray-300">{{ c }}</span>
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

      <!-- 雷达图 + 三维评分 -->
      <div class="flex gap-6 flex-wrap mb-4">
        <RadarChart :scores="data.scores" />
        <div class="flex-1 min-w-[260px] space-y-3">
          <div v-for="dim in scoreDims" :key="dim.key"
            class="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 flex items-center justify-between">
            <span class="text-gray-400 text-sm">{{ dim.label }}</span>
            <span class="font-mono font-semibold text-lg" :class="scoreColor(data.scores?.[dim.key])">
              {{ data.scores?.[dim.key] ?? '-' }}
            </span>
          </div>
          <!-- 基本面 & 消息面参考 -->
          <div class="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3">
            <div class="text-gray-500 text-xs mb-2">基本面参考</div>
            <div class="flex flex-wrap gap-x-5 gap-y-1 text-xs font-mono">
              <span>PE <span class="text-gray-200">{{ data.raw?.pe ?? '-' }}</span></span>
              <span>PB <span class="text-gray-200">{{ data.raw?.pb ?? '-' }}</span></span>
              <span>ROE <span class="text-gray-200">{{ data.raw?.roe != null ? data.raw.roe + '%' : '-' }}</span></span>
              <span>净利增速 <span class="text-gray-200">{{ data.raw?.profit_growth_yoy != null ? data.raw.profit_growth_yoy + '%' : '-' }}</span></span>
            </div>
          </div>
          <div class="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3">
            <div class="text-gray-500 text-xs mb-2">消息面参考</div>
            <div class="flex flex-wrap gap-x-5 gap-y-1 text-xs font-mono">
              <span>近30日研报 <span class="text-gray-200">{{ data.raw?.report_count ?? '-' }}</span></span>
              <span>评级 <span class="text-gray-200">{{ data.raw?.report_rating ?? '-' }}</span></span>
            </div>
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

const scoreDims = [
  { key: 'technical', label: '技术面' },
  { key: 'capital', label: '资金面' },
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
