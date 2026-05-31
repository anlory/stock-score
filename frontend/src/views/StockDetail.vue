<template>
  <div class="detail-page">
    <!-- Loading skeleton -->
    <div v-if="!data" class="space-y-5 py-8 anim-fade-in">
      <div class="flex items-center gap-4">
        <div class="skeleton h-9 w-40 rounded-lg"></div>
        <div class="skeleton h-6 w-20 rounded-md"></div>
      </div>
      <div class="skeleton h-36 rounded-xl"></div>
      <div class="skeleton h-24 rounded-xl"></div>
      <div class="skeleton h-24 rounded-xl"></div>
    </div>

    <!-- No data -->
    <template v-else-if="data?.error && !collectLoading">
      <div class="empty-state-detail">
        <div class="empty-icon-lg">
          <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M16 16s-1.5-2-4-2-4 2-4 2M9 9h.01M15 9h.01"/></svg>
        </div>
        <p class="text-white/30 text-sm mt-4">该股票暂无评分数据</p>
      </div>
    </template>

    <!-- Collecting -->
    <template v-else-if="collectLoading">
      <div class="collecting-state">
        <div class="collecting-spinner"></div>
        <p class="text-white/40 text-sm mt-5">正在采集数据并评分</p>
        <p class="text-white/20 text-xs mt-1">通常需要 5-15 秒</p>
      </div>
    </template>

    <!-- Main content -->
    <template v-else>
      <!-- Hero Header -->
      <header class="hero-header anim-slide-up">
        <button @click="$router.back()" class="back-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
          返回
        </button>

        <div class="hero-main">
          <div class="hero-info">
            <h1 class="hero-title">{{ data.name }}</h1>
            <span class="hero-code">{{ data.code }}</span>
            <a v-if="stockMarket === 'US'" :href="`https://finance.yahoo.com/quote/${data.code}`" target="_blank" class="hero-link">Yahoo Finance ↗</a>
            <a v-else-if="stockMarket === 'HK'" :href="`https://finance.yahoo.com/quote/${String(parseInt(data.code)).padStart(4, '0')}.HK`" target="_blank" class="hero-link">Yahoo Finance ↗</a>
            <a v-else :href="`https://stockpage.10jqka.com.cn/${data.code}/`" target="_blank" class="hero-link">同花顺 ↗</a>
          </div>

          <div class="hero-actions">
            <button v-if="isWatchlist" @click="removeWatch" class="watchlist-btn watched">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
              已加自选
            </button>
            <button v-else @click="addWatch" class="watchlist-btn">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
              加自选
            </button>

            <div v-if="data.short_term || data.trend" class="score-pills">
              <span v-if="data.short_term" class="score-pill pill-amber">
                <span class="pill-label">短线</span>
                <span class="pill-value">{{ data.short_term.total }}</span>
              </span>
              <span v-if="data.trend" class="score-pill pill-blue">
                <span class="pill-label">趋势</span>
                <span class="pill-value">{{ data.trend.total }}</span>
              </span>
            </div>
          </div>
        </div>
      </header>

      <!-- Company Profile -->
      <section class="detail-card stagger" style="--stagger: 1">
        <div class="card-header">
          <h2 class="card-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>
            公司概况
          </h2>
        </div>
        <div v-if="profile" class="profile-content">
          <div v-if="profile.introduction" class="profile-intro">
            <span :class="{ 'line-clamp-3': !showFullBiz }">{{ profile.introduction }}</span>
            <button v-if="profile.introduction.length > 80"
              @click="showFullBiz = !showFullBiz"
              class="expand-btn">{{ showFullBiz ? '收起' : '展开全文' }}</button>
          </div>
          <div v-if="profile.main_business" class="profile-biz">
            <span class="biz-label">主营</span>
            {{ profile.main_business }}
          </div>
          <div class="tag-row">
            <span v-if="profile.industry" class="tag tag-industry">{{ profile.industry }}</span>
            <span v-for="c in profile.concepts" :key="c" class="tag tag-concept">{{ c }}</span>
          </div>
          <div class="info-grid">
            <div v-if="profile.chairman" class="info-cell"><span class="info-label">董事长</span><span class="info-value">{{ profile.chairman }}</span></div>
            <div v-if="profile.manager" class="info-cell"><span class="info-label">总经理</span><span class="info-value">{{ profile.manager }}</span></div>
            <div v-if="profile.setup_date" class="info-cell"><span class="info-label">成立</span><span class="info-value">{{ profile.setup_date }}</span></div>
            <div v-if="profile.list_date" class="info-cell"><span class="info-label">上市</span><span class="info-value">{{ profile.list_date }}</span></div>
            <div v-if="profile.province || profile.city" class="info-cell"><span class="info-label">地区</span><span class="info-value">{{ [profile.province, profile.city].filter(Boolean).join(' ') }}</span></div>
            <div v-if="profile.employees" class="info-cell"><span class="info-label">员工</span><span class="info-value">{{ Math.round(profile.employees).toLocaleString() }}</span></div>
            <div v-if="profile.total_mv" class="info-cell"><span class="info-label">总市值</span><span class="info-value">{{ Math.round(profile.total_mv) }} 亿</span></div>
            <div v-if="profile.float_mv" class="info-cell"><span class="info-label">流通市值</span><span class="info-value">{{ Math.round(profile.float_mv) }} 亿</span></div>
            <div v-if="profile.total_share" class="info-cell"><span class="info-label">总股本</span><span class="info-value">{{ profile.total_share }} 亿</span></div>
            <div v-if="profile.float_share" class="info-cell"><span class="info-label">流通股</span><span class="info-value">{{ profile.float_share }} 亿</span></div>
            <div v-if="profile.pe" class="info-cell"><span class="info-label">PE</span><span class="info-value">{{ Math.round(profile.pe) }}</span></div>
            <div v-if="profile.pb" class="info-cell"><span class="info-label">PB</span><span class="info-value">{{ Math.round(profile.pb * 100) / 100 }}</span></div>
          </div>
          <div v-if="profile.office" class="profile-extra">
            <span class="extra-label">地址</span>{{ profile.office }}
          </div>
          <div v-if="profile.business" class="profile-extra">
            <span class="extra-label">经营范围</span>{{ profile.business }}
          </div>
        </div>
        <div v-else class="empty-hint">暂无公司资料</div>
      </section>

      <!-- Sector Tags -->
      <section class="detail-card stagger" style="--stagger: 2">
        <div class="card-header">
          <h2 class="card-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z"/></svg>
            板块关联
          </h2>
        </div>
        <div v-if="profile?.industry" class="tag-row">
          <span class="tag tag-industry">{{ profile.industry }}</span>
          <span v-for="c in profile.concepts" :key="c" class="tag tag-concept">{{ c }}</span>
        </div>
        <div v-else class="empty-hint">暂无板块数据</div>
      </section>

      <!-- Recent Trends -->
      <section class="detail-card stagger" style="--stagger: 3">
        <div class="card-header">
          <h2 class="card-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
            近期趋势
          </h2>
        </div>
        <div v-if="trendInfo" class="trend-content">
          <div class="trend-returns">
            <div class="return-item">
              <span class="return-label">近5日</span>
              <span class="return-value" :class="pctColor(trendInfo.return_5d)">{{ fmtPct(trendInfo.return_5d) }}</span>
            </div>
            <div class="return-item">
              <span class="return-label">近20日</span>
              <span class="return-value" :class="pctColor(trendInfo.return_20d)">{{ fmtPct(trendInfo.return_20d) }}</span>
            </div>
            <div class="return-item">
              <span class="return-label">近60日</span>
              <span class="return-value" :class="pctColor(trendInfo.return_60d)">{{ fmtPct(trendInfo.return_60d) }}</span>
            </div>
          </div>
          <div v-if="trendInfo.pattern_tags?.length" class="tag-row mt-3">
            <span v-for="t in trendInfo.pattern_tags" :key="t" class="tag tag-pattern">{{ t }}</span>
          </div>
        </div>
        <div v-else class="empty-hint">暂无近期趋势数据</div>
      </section>

      <!-- AI Analysis -->
      <section class="detail-card stagger" style="--stagger: 4">
        <div class="card-header">
          <h2 class="card-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2a4 4 0 0 1 4 4c0 1.95-1.4 3.58-3.25 3.93V12h3.75a2.5 2.5 0 0 1 2.5 2.5V15a4 4 0 1 1-2 0v-.5a.5.5 0 0 0-.5-.5H8a.5.5 0 0 0-.5.5V15a4 4 0 1 1-2 0v-.5A2.5 2.5 0 0 1 8 12h3.25V9.93A4.002 4.002 0 0 1 12 2z"/></svg>
            AI 综合研判
          </h2>
          <button @click="fetchAnalysis" :disabled="aiLoading" class="ai-trigger-btn" :class="{ loading: aiLoading }">
            <svg v-if="aiLoading" class="animate-spin w-3.5 h-3.5" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" stroke-dasharray="32" stroke-linecap="round"/></svg>
            <span>{{ aiLoading ? '分析中' : (data.ai_analysis ? '重新分析' : '开始分析') }}</span>
          </button>
        </div>
        <div v-if="aiLoading" class="ai-loading">
          <div class="ai-typing">
            <span></span><span></span><span></span>
          </div>
          <p class="text-white/30 text-xs mt-3">AI 正在深度分析中...</p>
        </div>
        <div v-else-if="aiError" class="ai-error">{{ aiError }}</div>
        <div v-else-if="displayAnalysis" class="ai-analysis text-gray-200 text-sm leading-relaxed" v-html="displayAnalysis"></div>
        <div v-else class="ai-placeholder">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" class="text-white/8"><path d="M12 2a4 4 0 0 1 4 4c0 1.95-1.4 3.58-3.25 3.93V12h3.75a2.5 2.5 0 0 1 2.5 2.5V15a4 4 0 1 1-2 0v-.5a.5.5 0 0 0-.5-.5H8a.5.5 0 0 0-.5.5V15a4 4 0 1 1-2 0v-.5A2.5 2.5 0 0 1 8 12h3.25V9.93A4.002 4.002 0 0 1 12 2z"/></svg>
          <p class="text-white/20 text-xs mt-2">点击「开始分析」获取 AI 综合研判</p>
        </div>
      </section>

      <!-- Radar + Scores -->
      <div class="scores-layout stagger" style="--stagger: 5">
        <RadarChart :scores="data.scores" />
        <div class="scores-column">
          <div v-for="dim in scoreDims" :key="dim.key" class="score-bar-card">
            <div class="score-bar-header">
              <span class="score-bar-label">{{ dim.label }}</span>
              <span class="score-bar-value" :class="scoreColorClass(data.scores?.[dim.key])">
                {{ data.scores?.[dim.key] ?? '-' }}
              </span>
            </div>
            <div class="score-bar-track">
              <div class="score-bar-fill" :class="scoreBarClass(data.scores?.[dim.key])"
                :style="{ width: (data.scores?.[dim.key] || 0) + '%' }"></div>
            </div>
          </div>

          <!-- Fundamentals -->
          <div class="meta-card">
            <div class="meta-title">基本面参考</div>
            <div class="meta-grid">
              <div class="meta-item"><span class="meta-key">PE</span><span class="meta-val">{{ data.raw?.pe ?? '-' }}</span></div>
              <div class="meta-item"><span class="meta-key">PB</span><span class="meta-val">{{ data.raw?.pb ?? '-' }}</span></div>
              <div class="meta-item"><span class="meta-key">ROE</span><span class="meta-val">{{ data.raw?.roe != null ? data.raw.roe + '%' : '-' }}</span></div>
              <div class="meta-item"><span class="meta-key">净利增速</span><span class="meta-val">{{ data.raw?.profit_growth_yoy != null ? data.raw.profit_growth_yoy + '%' : '-' }}</span></div>
            </div>
          </div>
          <div class="meta-card">
            <div class="meta-title">消息面参考</div>
            <div class="meta-grid">
              <div class="meta-item"><span class="meta-key">近30日研报</span><span class="meta-val">{{ data.raw?.report_count ?? '-' }}</span></div>
              <div class="meta-item"><span class="meta-key">评级</span><span class="meta-val">{{ data.raw?.report_rating ?? '-' }}</span></div>
            </div>
          </div>
        </div>
      </div>

      <!-- K-line Chart -->
      <section class="detail-card stagger" style="--stagger: 6">
        <div class="card-header">
          <h2 class="card-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 3v18h18"/><path d="M7 16l4-8 4 4 5-9"/></svg>
            K线图 · TradingView
          </h2>
        </div>
        <TradingViewChart :code="route.params.code" />
      </section>

      <!-- Raw Data (collapsible) -->
      <section class="detail-card stagger" style="--stagger: 7">
        <button @click="showRaw = !showRaw" class="raw-toggle">
          <span class="card-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            原始指标数据
          </span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="transition-transform duration-200" :class="showRaw ? 'rotate-180' : ''"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
        <Transition name="collapse">
          <div v-if="showRaw" class="raw-grid">
            <div v-for="(val, key) in displayRaw" :key="key" class="raw-cell">
              <span class="raw-key">{{ key }}</span>
              <span class="raw-val">{{ val ?? '-' }}</span>
            </div>
          </div>
        </Transition>
      </section>
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
const stockMarket = ref('SH')

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

function scoreColorClass(s) {
  if (!s && s !== 0) return 'text-white/25'
  if (s >= 75) return 'text-emerald-400'
  if (s >= 50) return 'text-amber-400'
  return 'text-red-400'
}
function scoreBarClass(s) {
  if (!s && s !== 0) return 'bar-none'
  if (s >= 75) return 'bar-high'
  if (s >= 50) return 'bar-mid'
  return 'bar-low'
}
function pctColor(v) {
  if (v === null || v === undefined) return 'text-white/25'
  return v > 0 ? 'text-red-400' : (v < 0 ? 'text-emerald-400' : 'text-white/50')
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
  if (prof.status === 'fulfilled' && prof.value) {
    profile.value = prof.value
    stockMarket.value = prof.value.market || 'SH'
  }
  if (watched.status === 'fulfilled') isWatchlist.value = watched.value
  aiResult.value = ''
  aiError.value = ''
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
.detail-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px 24px 64px;
}

/* ── Hero ──────────────────────────────────────── */
.hero-header {
  margin-bottom: 24px;
}
.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  font-size: 13px;
  font-weight: 500;
  color: rgba(148, 163, 184, 0.4);
  background: none;
  border: none;
  cursor: pointer;
  font-family: 'DM Sans', sans-serif;
  transition: color 200ms;
  margin-bottom: 16px;
}
.back-btn:hover { color: rgba(241, 245, 249, 0.7); }

.hero-main {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.hero-info {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}
.hero-title {
  font-size: 26px;
  font-weight: 700;
  color: #f1f5f9;
  letter-spacing: -0.5px;
}
.hero-code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  color: rgba(148, 163, 184, 0.35);
}
.hero-link {
  font-size: 12px;
  color: rgba(96, 165, 250, 0.6);
  text-decoration: none;
  transition: color 150ms;
}
.hero-link:hover { color: #93bbfd; }

.hero-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* ── Watchlist Button ──────────────────────────── */
.watchlist-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  font-family: 'DM Sans', sans-serif;
  cursor: pointer;
  border: 1px solid rgba(245, 158, 11, 0.2);
  background: rgba(245, 158, 11, 0.06);
  color: rgba(251, 191, 36, 0.8);
  transition: all 200ms cubic-bezier(0.16, 1, 0.3, 1);
}
.watchlist-btn:hover {
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.35);
}
.watchlist-btn.watched {
  border-color: rgba(148, 163, 184, 0.1);
  background: rgba(148, 163, 184, 0.04);
  color: rgba(148, 163, 184, 0.4);
}
.watchlist-btn.watched svg {
  fill: rgba(245, 158, 11, 0.3);
  stroke: rgba(245, 158, 11, 0.3);
}

/* ── Score Pills ───────────────────────────────── */
.score-pills {
  display: flex;
  gap: 8px;
}
.score-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 14px;
  border-radius: 20px;
  font-family: 'JetBrains Mono', monospace;
}
.pill-amber {
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.15);
}
.pill-blue {
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.15);
}
.pill-label {
  font-size: 11px;
  font-weight: 400;
  color: rgba(241, 245, 249, 0.4);
}
.pill-value {
  font-size: 16px;
  font-weight: 700;
}
.pill-amber .pill-value { color: #fbbf24; }
.pill-blue .pill-value { color: #60a5fa; }

/* ── Detail Card ───────────────────────────────── */
.detail-card {
  background: rgba(17, 24, 39, 0.45);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(148, 163, 184, 0.06);
  border-radius: 14px;
  padding: 20px;
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: rgba(241, 245, 249, 0.6);
}
.card-title svg {
  color: rgba(148, 163, 184, 0.25);
}

/* ── Profile ───────────────────────────────────── */
.profile-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.profile-intro {
  font-size: 13px;
  color: rgba(226, 232, 240, 0.7);
  line-height: 1.7;
}
.expand-btn {
  color: rgba(96, 165, 250, 0.7);
  background: none;
  border: none;
  cursor: pointer;
  font-size: 12px;
  font-family: 'DM Sans', sans-serif;
  margin-left: 4px;
  transition: color 150ms;
}
.expand-btn:hover { color: #93bbfd; }
.profile-biz {
  font-size: 12px;
  color: rgba(148, 163, 184, 0.5);
}
.biz-label {
  color: rgba(148, 163, 184, 0.3);
  margin-right: 4px;
}

/* ── Tags ──────────────────────────────────────── */
.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tag {
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
}
.tag-industry {
  background: rgba(59, 130, 246, 0.1);
  color: rgba(96, 165, 250, 0.8);
  border: 1px solid rgba(59, 130, 246, 0.15);
}
.tag-concept {
  background: rgba(148, 163, 184, 0.05);
  color: rgba(226, 232, 240, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.06);
}
.tag-pattern {
  background: rgba(245, 158, 11, 0.06);
  color: rgba(251, 191, 36, 0.7);
  border: 1px solid rgba(245, 158, 11, 0.1);
}

/* ── Info Grid ─────────────────────────────────── */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 8px;
}
.info-cell {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
}
.info-label {
  color: rgba(148, 163, 184, 0.3);
  flex-shrink: 0;
}
.info-value {
  color: rgba(226, 232, 240, 0.7);
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}
.profile-extra {
  font-size: 11px;
  color: rgba(148, 163, 184, 0.35);
  line-height: 1.6;
}
.extra-label {
  color: rgba(148, 163, 184, 0.2);
  margin-right: 4px;
}

/* ── Trend Returns ─────────────────────────────── */
.trend-returns {
  display: flex;
  gap: 24px;
}
.return-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.return-label {
  font-size: 11px;
  color: rgba(148, 163, 184, 0.3);
}
.return-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 15px;
  font-weight: 600;
}

/* ── AI Section ────────────────────────────────── */
.ai-trigger-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 14px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  font-family: 'DM Sans', sans-serif;
  cursor: pointer;
  border: 1px solid rgba(59, 130, 246, 0.2);
  background: rgba(59, 130, 246, 0.08);
  color: rgba(96, 165, 250, 0.8);
  transition: all 200ms;
}
.ai-trigger-btn:hover:not(:disabled) {
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.3);
}
.ai-trigger-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ai-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 0;
}
.ai-typing {
  display: flex;
  gap: 5px;
}
.ai-typing span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(96, 165, 250, 0.3);
  animation: typingBounce 1.4s ease-in-out infinite;
}
.ai-typing span:nth-child(2) { animation-delay: 0.2s; }
.ai-typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typingBounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.3; }
  30% { transform: translateY(-6px); opacity: 1; }
}
.ai-error {
  color: #f87171;
  font-size: 12px;
  padding: 4px 0;
}
.ai-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 28px 0;
}
.ai-analysis :deep(p) { margin: 0.4em 0; }
.ai-analysis :deep(ul), .ai-analysis :deep(ol) { margin: 0.4em 0; padding-left: 1.5em; }
.ai-analysis :deep(li) { margin: 0.2em 0; }
.ai-analysis :deep(strong) { color: #93c5fd; font-weight: 600; }
.ai-analysis :deep(h1), .ai-analysis :deep(h2), .ai-analysis :deep(h3) {
  color: #e5e7eb; font-weight: 700; margin: 0.6em 0 0.3em; font-size: 0.95rem;
}
.line-clamp-3 {
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}

/* ── Scores Layout ─────────────────────────────── */
.scores-layout {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.scores-column {
  flex: 1;
  min-width: 280px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ── Score Bar Card ────────────────────────────── */
.score-bar-card {
  background: rgba(17, 24, 39, 0.45);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(148, 163, 184, 0.06);
  border-radius: 12px;
  padding: 14px 16px;
}
.score-bar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.score-bar-label {
  font-size: 13px;
  color: rgba(148, 163, 184, 0.5);
}
.score-bar-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 18px;
  font-weight: 700;
}
.score-bar-track {
  width: 100%;
  height: 4px;
  background: rgba(148, 163, 184, 0.06);
  border-radius: 2px;
  overflow: hidden;
}
.score-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}
.bar-high { background: linear-gradient(90deg, rgba(34, 197, 94, 0.5), rgba(34, 197, 94, 0.8)); }
.bar-mid { background: linear-gradient(90deg, rgba(245, 158, 11, 0.5), rgba(245, 158, 11, 0.8)); }
.bar-low { background: linear-gradient(90deg, rgba(239, 68, 68, 0.5), rgba(239, 68, 68, 0.8)); }
.bar-none { background: rgba(148, 163, 184, 0.15); }

/* ── Meta Card ─────────────────────────────────── */
.meta-card {
  background: rgba(17, 24, 39, 0.45);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(148, 163, 184, 0.06);
  border-radius: 12px;
  padding: 14px 16px;
}
.meta-title {
  font-size: 11px;
  color: rgba(148, 163, 184, 0.3);
  margin-bottom: 8px;
  font-weight: 500;
}
.meta-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
}
.meta-item {
  font-size: 12px;
}
.meta-key {
  color: rgba(148, 163, 184, 0.35);
  margin-right: 4px;
}
.meta-val {
  font-family: 'JetBrains Mono', monospace;
  color: rgba(226, 232, 240, 0.7);
}

/* ── Raw Toggle ────────────────────────────────── */
.raw-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  color: inherit;
}
.raw-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
  margin-top: 16px;
}
@media (max-width: 768px) {
  .raw-grid { grid-template-columns: repeat(2, 1fr); }
}
.raw-cell {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.04);
  font-size: 11px;
}
.raw-key {
  color: rgba(148, 163, 184, 0.3);
}
.raw-val {
  font-family: 'JetBrains Mono', monospace;
  color: rgba(226, 232, 240, 0.6);
}

/* ── Collapse transition ───────────────────────── */
.collapse-enter-active { transition: all 300ms cubic-bezier(0.16, 1, 0.3, 1); }
.collapse-leave-active { transition: all 200ms ease-in; }
.collapse-enter-from, .collapse-leave-to {
  opacity: 0;
  max-height: 0;
  overflow: hidden;
}
.collapse-enter-to, .collapse-leave-from {
  max-height: 1000px;
}

/* ── Empty & Loading States ────────────────────── */
.empty-state-detail {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80px 0;
  animation: fadeIn 400ms both;
}
.empty-icon-lg { color: rgba(148, 163, 184, 0.08); }
.empty-hint {
  color: rgba(148, 163, 184, 0.2);
  font-size: 12px;
  padding: 8px 0;
}
.collecting-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80px 0;
  animation: fadeIn 400ms both;
}
.collecting-spinner {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 3px solid rgba(148, 163, 184, 0.08);
  border-top-color: rgba(245, 158, 11, 0.4);
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
