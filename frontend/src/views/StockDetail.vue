<template>
  <div class="p-6 max-w-5xl mx-auto">
    <button @click="$router.back()" class="text-gray-400 hover:text-white mb-4 text-sm">← 返回</button>
    <div v-if="!data" class="text-gray-600 text-center py-20">加载中...</div>
    <template v-else>
      <div class="flex items-center gap-4 mb-6">
        <h1 class="text-2xl font-bold">{{ data.name }}</h1>
        <span class="font-mono text-gray-400">{{ data.code }}</span>
        <div class="ml-auto flex gap-3">
          <span v-if="data.short_term" class="bg-amber-900/40 text-amber-300 border border-amber-800/40 px-3 py-1 rounded-full font-mono font-bold text-lg">
            短线 {{ data.short_term.total }} 分
          </span>
          <span v-if="data.trend" class="bg-blue-900/40 text-blue-300 border border-blue-800/40 px-3 py-1 rounded-full font-mono font-bold text-lg">
            趋势 {{ data.trend.total }} 分
          </span>
        </div>
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm text-gray-400 font-semibold">AI 分析</span>
          <button @click="fetchAnalysis" :disabled="aiLoading"
            class="px-3 py-1 rounded text-xs transition-colors"
            :class="aiLoading ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-blue-800 text-white hover:bg-blue-700'"
          >{{ aiLoading ? '分析中...' : (data.ai_analysis ? '重新分析' : '开始分析') }}</button>
        </div>
        <div v-if="aiLoading" class="text-gray-500 text-center py-4 text-xs">AI 正在分析中...</div>
        <div v-else-if="aiError" class="text-red-400 text-xs py-1">{{ aiError }}</div>
        <div v-else-if="displayAnalysis" class="ai-analysis text-gray-200 text-sm leading-relaxed" v-html="displayAnalysis"></div>
        <div v-else class="text-gray-600 text-center py-4 text-xs">点击"开始分析"获取 AI 综合研判</div>
      </div>
      <div class="flex gap-6 flex-wrap mb-6">
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
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h2 class="text-sm text-gray-400 mb-3 font-semibold">原始指标数据</h2>
        <div class="grid grid-cols-3 gap-2 text-xs font-mono">
          <div v-for="(val, key) in displayRaw" :key="key" class="flex justify-between border-b border-gray-800/50 py-1">
            <span class="text-gray-500">{{ key }}</span>
            <span class="text-gray-200">{{ val ?? '-' }}</span>
          </div>
        </div>
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4 mt-4">
        <h2 class="text-sm text-gray-400 mb-3 font-semibold">日K线</h2>
        <div v-if="klineLoading" class="text-gray-500 text-center py-10 text-sm">K线加载中...</div>
        <div v-else-if="klineData.length"><KlineChart :data="klineData" /></div>
        <div v-else class="text-gray-600 text-center py-10 text-sm">暂无K线数据</div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import RadarChart from '../components/RadarChart.vue'
import KlineChart from '../components/KlineChart.vue'
import { getStockDetail, getKline, getAnalysis } from '../api'

// marked 对中文 **加粗** 识别不好，预处理为 <strong>
function preprocessBold(text) {
  return text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
}

const route = useRoute()
const data = ref(null)
const klineData = ref([])
const klineLoading = ref(false)
const aiResult = ref('')
const aiLoading = ref(false)
const aiError = ref('')
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
const SKIP = new Set(['code', 'date', '_sa_instance_state', 'ai_analysis'])
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
async function load() {
  data.value = await getStockDetail(route.params.code)
  aiResult.value = ''
  aiError.value = ''
  klineLoading.value = true
  try {
    klineData.value = await getKline(route.params.code, 60)
  } catch { klineData.value = [] }
  klineLoading.value = false
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
.ai-analysis :deep(h1), .ai-analysis :deep(h2), .ai-analysis :deep(h3) { color: #e5e7eb; font-weight: 700; margin: 0.6em 0 0.3em; }
</style>
