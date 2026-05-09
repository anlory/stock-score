<template>
  <!-- 港美股 -->
  <div v-if="isHKUS" class="p-6">
    <div class="flex items-center justify-between mb-4">
      <div class="flex gap-5 border-b border-gray-800">
        <button v-for="t in hkUsTabs" :key="t.value"
          @click="hkUsTab = t.value"
          class="pb-2 text-sm font-medium border-b-2 transition-colors"
          :class="hkUsTab === t.value ? 'border-amber-400 text-amber-400' : 'border-transparent text-gray-500 hover:text-gray-300'">
          {{ t.label }}
        </button>
      </div>
      <div class="flex gap-3 border-b border-gray-800">
        <button v-for="s in strategyTabs" :key="s.value"
          @click="strategy = s.value"
          class="pb-2 text-sm font-medium border-b-2 transition-colors"
          :class="strategy === s.value ? 'border-amber-400 text-amber-400' : 'border-transparent text-gray-500 hover:text-gray-300'">
          {{ s.label }}
        </button>
      </div>
    </div>
    <ScoreTable :rows="rows" :strategy="strategy" />
    <div v-if="!rows.length && !loading" class="text-center py-12 text-gray-600">暂无数据，请先触发同步</div>
  </div>

  <!-- A股 / 自选 -->
  <div v-else class="p-6">
    <div class="flex items-center justify-between mb-4">
      <div class="flex gap-5 border-b border-gray-800">
        <button v-for="s in strategyTabs" :key="s.value"
          @click="strategy = s.value"
          class="pb-2 text-sm font-medium border-b-2 transition-colors"
          :class="strategy === s.value ? 'border-amber-400 text-amber-400' : 'border-transparent text-gray-500 hover:text-gray-300'">
          {{ s.label }}
        </button>
      </div>
      <button @click="showGuide = !showGuide"
        class="bg-gray-800 border rounded-md px-2.5 py-1 text-xs transition-colors"
        :class="showGuide ? 'border-blue-500 text-blue-400' : 'border-gray-700 text-gray-400 hover:text-gray-200'">
        ? 评分说明
      </button>
    </div>

    <div v-if="showGuide" class="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-4">
      <h3 class="text-amber-400 text-sm font-bold mb-3">{{ currentStrategyLabel }}权重</h3>
      <div class="grid grid-cols-3 gap-4">
        <div v-for="d in currentDimensions" :key="d.key" class="bg-gray-950 rounded-lg p-3" :style="{ borderTop: `2px solid ${d.color}` }">
          <div class="font-bold text-xs" :style="{ color: d.color }">{{ d.label }}</div>
          <div class="text-gray-500 text-xs mt-1.5 leading-relaxed">{{ d.desc }}</div>
        </div>
      </div>
    </div>

    <ScoreTable :rows="rows" :strategy="strategy" @added="load" />
    <div v-if="!rows.length && !loading" class="text-center py-12 text-gray-600">暂无数据，请先触发同步</div>
  </div>
</template>

<script setup>
import { ref, shallowRef, watch, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import ScoreTable from '../components/ScoreTable.vue'
import { getLeaderboard } from '../api'

const route = useRoute()
const strategy = ref('short_term')
const rows = shallowRef([])
const loading = ref(false)
const showGuide = ref(false)

const isHKUS = computed(() => route.path === '/hk')

const hkUsTabs = [
  { value: 'hsi', label: '恒生指数', market: 'HK' },
  { value: 'hstech', label: '恒生科技', market: 'HK' },
  { value: 'sp500', label: 'S&P 500', market: 'US' },
  { value: 'nasdaq100', label: '纳斯达克100', market: 'US' },
]
const hkUsTab = ref('hsi')

const strategyTabs = computed(() => {
  if (isHKUS.value) {
    return [
      { value: 'short_term', label: '短线策略' },
      { value: 'trend', label: '趋势策略' },
    ]
  }
  return [
    { value: 'short_term', label: '短线策略' },
    { value: 'trend', label: '趋势策略' },
    { value: 'setup', label: '埋伏策略' },
  ]
})

const currentStrategyLabel = computed(() =>
  strategyTabs.value.find(s => s.value === strategy.value)?.label || ''
)

const strategyDescriptions = {
  short_term: {
    technical: { key: 'technical', label: '技术面 35%', color: '#60a5fa', desc: '价格动量45分 · 量能配合30分 · 趋势结构15分 · 趋势健康10分' },
    capital: { key: 'capital', label: '资金面 25%', color: '#f59e0b', desc: '主力净流入 · 超大单净流入' },
    heat: { key: 'heat', label: '市场热度 40%', color: '#fb923c', desc: '涨跌幅 · 换手率 · 量比 · 连板天数' },
  },
  trend: {
    technical: { key: 'technical', label: '技术面 55%', color: '#60a5fa', desc: '13日爆发力18分 · 攻击放量20分 · 均线排列10分 · 双通道健康10分' },
    capital: { key: 'capital', label: '资金面 30%', color: '#f59e0b', desc: '主力净流入 · 超大单净流入 · 资金趋势确认' },
    heat: { key: 'heat', label: '市场热度 15%', color: '#fb923c', desc: '涨跌幅 · 换手率 · 量比' },
  },
  setup: {
    setup: { key: 'setup', label: '蓄势信号 55%', color: '#a78bfa', desc: '底部缩量11 · 温和放量8 · 均线收敛8 · 金叉信号11 · 跌幅充分6 · MA5斜率+站上8 · RSI低位3' },
    capital: { key: 'capital', label: '资金面(温和) 30%', color: '#f59e0b', desc: '温和净流入15 · 持续流入10 · 超大单不流出5' },
    heat: { key: 'heat', label: '热度面(低热度) 15%', color: '#fb923c', desc: '低换手8 · 低振幅4 · 量比适中3' },
  },
}

const strategyDimensions = {
  short_term: Object.values(strategyDescriptions.short_term),
  trend: Object.values(strategyDescriptions.trend),
  setup: Object.values(strategyDescriptions.setup),
}
const currentDimensions = computed(() => strategyDimensions[strategy.value] || [])

function getMarketFilter() {
  if (!isHKUS.value) return undefined
  const tab = hkUsTabs.find(t => t.value === hkUsTab.value)
  return tab?.market
}

async function load() {
  if (isHKUS.value && !hkUsTab.value) return
  loading.value = true
  try {
    const res = await getLeaderboard(
      isHKUS.value ? 'other' : (route.path === '/watchlist' ? 'watchlist' : 'other'),
      strategy.value,
      getMarketFilter()
    )
    rows.value = res.stocks || []
  } catch { rows.value = [] }
  loading.value = false
}

watch(strategy, load)
watch(hkUsTab, load)
watch(() => route.path, load)
onMounted(load)
</script>
