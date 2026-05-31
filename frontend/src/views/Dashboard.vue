<template>
  <!-- 港美股 -->
  <div v-if="isHKUS" class="page-container">
    <div class="flex items-center justify-between mb-5 anim-slide-up">
      <div class="tab-group">
        <button v-for="t in hkUsTabs" :key="t.value"
          @click="hkUsTab = t.value"
          class="tab-item" :class="hkUsTab === t.value ? 'tab-active' : 'tab-inactive'">
          {{ t.label }}
        </button>
      </div>
      <div class="tab-group">
        <button v-for="s in strategyTabs" :key="s.value"
          @click="strategy = s.value"
          class="tab-item" :class="strategy === s.value ? 'tab-active-amber' : 'tab-inactive'">
          {{ s.label }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="space-y-3">
      <div v-for="i in 8" :key="i" class="skeleton h-12 rounded-lg"></div>
    </div>
    <template v-else>
      <ScoreTable :rows="rows" :strategy="strategy" />
      <div v-if="!rows.length" class="empty-state">
        <div class="empty-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round"><path d="M3 3v18h18"/><path d="M7 16l4-8 4 4 5-9"/></svg>
        </div>
        <p class="text-white/30 text-sm mt-4">暂无数据</p>
        <p class="text-white/15 text-xs mt-1">点击右上角「同步」获取数据</p>
      </div>
    </template>
  </div>

  <!-- A股 / 自选 -->
  <div v-else class="page-container">
    <div class="flex items-center justify-between mb-5 anim-slide-up">
      <div class="tab-group">
        <button v-for="s in strategyTabs" :key="s.value"
          @click="strategy = s.value"
          class="tab-item" :class="strategy === s.value ? 'tab-active-amber' : 'tab-inactive'">
          {{ s.label }}
        </button>
      </div>
      <button @click="showGuide = !showGuide"
        class="guide-toggle" :class="{ active: showGuide }">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><circle cx="12" cy="17" r="0.5"/></svg>
        评分说明
      </button>
    </div>

    <!-- Scoring Guide -->
    <Transition name="guide">
      <div v-if="showGuide" class="guide-container mb-5">
        <div class="guide-header">
          <h3 class="guide-title">{{ currentStrategyLabel }}权重分布</h3>
        </div>
        <div class="guide-grid">
          <div v-for="(d, i) in currentDimensions" :key="d.key" class="guide-card stagger" :style="{ '--stagger': i }">
            <div class="guide-card-accent" :style="{ background: d.color }"></div>
            <div class="guide-card-body">
              <div class="guide-card-label" :style="{ color: d.color }">{{ d.label }}</div>
              <div class="guide-card-desc">{{ d.desc }}</div>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <div v-if="loading" class="space-y-3">
      <div v-for="i in 8" :key="i" class="skeleton h-12 rounded-lg"></div>
    </div>
    <template v-else>
      <ScoreTable :rows="rows" :strategy="strategy" @added="load" />
      <div v-if="!rows.length" class="empty-state">
        <div class="empty-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round"><path d="M3 3v18h18"/><path d="M7 16l4-8 4 4 5-9"/></svg>
        </div>
        <p class="text-white/30 text-sm mt-4">暂无数据</p>
        <p class="text-white/15 text-xs mt-1">点击右上角「同步」获取数据</p>
      </div>
    </template>
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

<style scoped>
.page-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 24px 48px;
}

/* ── Tab group ─────────────────────────────────── */
.tab-group {
  display: flex;
  gap: 2px;
  background: rgba(148, 163, 184, 0.04);
  border-radius: 10px;
  padding: 3px;
}
.tab-item {
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  font-family: 'DM Sans', sans-serif;
  cursor: pointer;
  border: none;
  transition: all 200ms cubic-bezier(0.16, 1, 0.3, 1);
}
.tab-active {
  background: rgba(148, 163, 184, 0.1);
  color: #f1f5f9;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}
.tab-active-amber {
  background: rgba(245, 158, 11, 0.12);
  color: #fbbf24;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}
.tab-inactive {
  background: transparent;
  color: rgba(148, 163, 184, 0.5);
}
.tab-inactive:hover {
  color: rgba(241, 245, 249, 0.7);
  background: rgba(148, 163, 184, 0.04);
}

/* ── Guide toggle ──────────────────────────────── */
.guide-toggle {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  font-family: 'DM Sans', sans-serif;
  cursor: pointer;
  border: 1px solid rgba(148, 163, 184, 0.08);
  background: transparent;
  color: rgba(148, 163, 184, 0.4);
  transition: all 200ms cubic-bezier(0.16, 1, 0.3, 1);
}
.guide-toggle:hover {
  color: rgba(241, 245, 249, 0.7);
  border-color: rgba(148, 163, 184, 0.15);
}
.guide-toggle.active {
  color: rgba(96, 165, 250, 0.8);
  border-color: rgba(96, 165, 250, 0.25);
  background: rgba(96, 165, 250, 0.06);
}

/* ── Guide container ───────────────────────────── */
.guide-container {
  background: rgba(17, 24, 39, 0.5);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(148, 163, 184, 0.08);
  border-radius: 14px;
  padding: 20px;
  overflow: hidden;
}
.guide-header {
  margin-bottom: 16px;
}
.guide-title {
  font-size: 13px;
  font-weight: 600;
  color: #fbbf24;
}
.guide-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
@media (max-width: 768px) {
  .guide-grid { grid-template-columns: 1fr; }
}
.guide-card {
  display: flex;
  gap: 12px;
  background: rgba(6, 8, 15, 0.5);
  border-radius: 10px;
  padding: 14px;
  border: 1px solid rgba(148, 163, 184, 0.05);
}
.guide-card-accent {
  width: 3px;
  border-radius: 2px;
  flex-shrink: 0;
}
.guide-card-label {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
}
.guide-card-desc {
  font-size: 11px;
  color: rgba(148, 163, 184, 0.5);
  line-height: 1.6;
}

/* ── Guide transition ──────────────────────────── */
.guide-enter-active { transition: all 300ms cubic-bezier(0.16, 1, 0.3, 1); }
.guide-leave-active { transition: all 200ms ease-in; }
.guide-enter-from, .guide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
  max-height: 0;
  margin-bottom: 0;
  padding: 0 20px;
}
.guide-enter-to, .guide-leave-from {
  max-height: 300px;
}

/* ── Empty state ───────────────────────────────── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 64px 0;
  animation: fadeIn 400ms cubic-bezier(0.16, 1, 0.3, 1) both;
}
.empty-icon {
  color: rgba(148, 163, 184, 0.12);
}
</style>
