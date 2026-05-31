<template>
  <div class="table-wrapper">
    <table class="score-table">
      <thead>
        <tr class="table-header">
          <th class="th-rank">#</th>
          <th class="th-name">股票</th>
          <th class="th-score">总分</th>
          <th v-if="strategy !== 'setup'" class="th-dim">技术</th>
          <th v-if="strategy === 'setup'" class="th-dim">蓄势</th>
          <th class="th-dim">资金</th>
          <th class="th-dim">热度</th>
          <th class="th-action">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, idx) in rows" :key="row.code"
          class="table-row stagger"
          :style="{ '--stagger': idx }"
          @dblclick="$router.push('/stock/' + row.code)">
          <!-- Rank -->
          <td class="td-rank">
            <span v-if="idx < 3" class="rank-badge" :class="'rank-' + (idx + 1)">{{ idx + 1 }}</span>
            <span v-else class="rank-num">{{ idx + 1 }}</span>
          </td>
          <!-- Name -->
          <td class="td-name">
            <div class="stock-identity">
              <span class="stock-name">{{ row.name }}</span>
              <span class="stock-code">{{ row.code }}</span>
            </div>
          </td>
          <!-- Total Score -->
          <td class="td-score">
            <div class="score-pill" :class="scoreTier(row.total_score)">
              <span class="score-value">{{ row.total_score != null ? Math.round(row.total_score) : '-' }}</span>
            </div>
          </td>
          <!-- Dimensions -->
          <td v-if="strategy !== 'setup'" class="td-dim">
            <span class="dim-value" :class="dimTier(row.technical_score)">{{ row.technical_score != null ? Math.round(row.technical_score) : '-' }}</span>
          </td>
          <td v-if="strategy === 'setup'" class="td-dim">
            <span class="dim-value" :class="dimTier(row.setup_score)">{{ row.setup_score != null ? Math.round(row.setup_score) : '-' }}</span>
          </td>
          <td class="td-dim">
            <span class="dim-value" :class="dimTier(row.capital_score)">{{ row.capital_score != null ? Math.round(row.capital_score) : '-' }}</span>
          </td>
          <td class="td-dim">
            <span class="dim-value" :class="dimTier(row.heat_score)">{{ row.heat_score != null ? Math.round(row.heat_score) : '-' }}</span>
          </td>
          <!-- Actions -->
          <td class="td-action">
            <button v-if="!row.is_watchlist" @click.stop="add(row)" class="action-btn action-add">+ 自选</button>
            <button v-else @click.stop="remove(row)" class="action-btn action-remove">移除</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { addWatchlist, removeWatchlist } from '../api'

const props = defineProps({ rows: Array, strategy: String })
const emit = defineEmits(['added'])

function scoreTier(s) {
  if (!s && s !== 0) return 'tier-none'
  if (s >= 75) return 'tier-high'
  if (s >= 50) return 'tier-mid'
  return 'tier-low'
}
function dimTier(s) {
  if (!s && s !== 0) return ''
  if (s >= 75) return 'dim-high'
  if (s >= 50) return 'dim-mid'
  return 'dim-low'
}
async function add(row) {
  await addWatchlist(row.code, row.name)
  emit('added')
}
async function remove(row) {
  await removeWatchlist(row.code)
  emit('added')
}
</script>

<style scoped>
.table-wrapper {
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.06);
}

.score-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

/* ── Header ────────────────────────────────────── */
.table-header {
  background: rgba(148, 163, 184, 0.03);
}
.th-rank {
  padding: 10px 12px;
  width: 48px;
  text-align: center;
  font-size: 11px;
  font-weight: 500;
  color: rgba(148, 163, 184, 0.3);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.th-name {
  padding: 10px 12px;
  text-align: left;
  font-size: 11px;
  font-weight: 500;
  color: rgba(148, 163, 184, 0.3);
}
.th-score {
  padding: 10px 12px;
  width: 80px;
  text-align: center;
  font-size: 11px;
  font-weight: 500;
  color: rgba(148, 163, 184, 0.3);
}
.th-dim {
  padding: 10px 12px;
  width: 64px;
  text-align: center;
  font-size: 11px;
  font-weight: 500;
  color: rgba(148, 163, 184, 0.3);
}
.th-action {
  padding: 10px 12px;
  min-width: 80px;
  text-align: center;
  font-size: 11px;
  font-weight: 500;
  color: rgba(148, 163, 184, 0.3);
}

/* ── Rows ──────────────────────────────────────── */
.table-row {
  border-top: 1px solid rgba(148, 163, 184, 0.04);
  cursor: pointer;
  transition: background 150ms;
}
.table-row:hover {
  background: rgba(245, 158, 11, 0.03);
}

/* ── Rank ──────────────────────────────────────── */
.td-rank {
  padding: 12px;
  text-align: center;
}
.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 7px;
  font-size: 11px;
  font-weight: 700;
  font-family: 'DM Sans', sans-serif;
}
.rank-1 {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(245, 158, 11, 0.1));
  color: #fbbf24;
  box-shadow: 0 0 8px rgba(245, 158, 11, 0.15);
}
.rank-2 {
  background: linear-gradient(135deg, rgba(148, 163, 184, 0.15), rgba(148, 163, 184, 0.08));
  color: #cbd5e1;
}
.rank-3 {
  background: linear-gradient(135deg, rgba(180, 120, 80, 0.15), rgba(180, 120, 80, 0.08));
  color: #d4a574;
}
.rank-num {
  font-size: 12px;
  color: rgba(148, 163, 184, 0.25);
  font-weight: 500;
}

/* ── Name ──────────────────────────────────────── */
.td-name {
  padding: 12px;
}
.stock-identity {
  display: flex;
  align-items: center;
  gap: 8px;
}
.stock-name {
  font-weight: 600;
  color: rgba(241, 245, 249, 0.9);
}
.stock-code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: rgba(148, 163, 184, 0.3);
}

/* ── Score Pill ────────────────────────────────── */
.td-score {
  padding: 12px;
  text-align: center;
}
.score-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  height: 28px;
  border-radius: 8px;
  padding: 0 10px;
}
.tier-high {
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.15);
}
.tier-high .score-value { color: #4ade80; }
.tier-mid {
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.12);
}
.tier-mid .score-value { color: #fbbf24; }
.tier-low {
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.12);
}
.tier-low .score-value { color: #f87171; }
.tier-none {
  background: rgba(148, 163, 184, 0.04);
  border: 1px solid rgba(148, 163, 184, 0.06);
}
.tier-none .score-value { color: rgba(148, 163, 184, 0.3); }
.score-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 600;
}

/* ── Dimension Values ──────────────────────────── */
.td-dim {
  padding: 12px;
  text-align: center;
}
.dim-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 500;
  color: rgba(148, 163, 184, 0.35);
}
.dim-high { color: rgba(74, 222, 128, 0.7); }
.dim-mid { color: rgba(251, 191, 36, 0.7); }
.dim-low { color: rgba(248, 113, 113, 0.6); }

/* ── Actions ───────────────────────────────────── */
.td-action {
  padding: 12px;
  text-align: center;
}
.action-btn {
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  font-family: 'DM Sans', sans-serif;
  cursor: pointer;
  border: none;
  white-space: nowrap;
  transition: all 150ms cubic-bezier(0.16, 1, 0.3, 1);
}
.action-add {
  background: rgba(245, 158, 11, 0.08);
  color: rgba(251, 191, 36, 0.8);
}
.action-add:hover {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}
.action-remove {
  background: rgba(239, 68, 68, 0.06);
  color: rgba(248, 113, 113, 0.5);
}
.action-remove:hover {
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
}
</style>
