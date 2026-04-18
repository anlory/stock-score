<template>
  <div class="p-6">
    <div class="flex items-center gap-3 mb-6">
      <button
        v-for="s in strategies"
        :key="s.value"
        @click="strategy = s.value"
        class="px-4 py-1.5 rounded text-sm font-medium transition-colors"
        :class="strategy === s.value ? 'bg-blue-800 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'"
      >{{ s.label }}</button>
    </div>
    <div class="flex gap-4 border-b border-gray-800 mb-4">
      <button
        v-for="t in tabs"
        :key="t.value"
        @click="tab = t.value"
        class="pb-2 text-sm font-medium border-b-2 transition-colors"
        :class="tab === t.value ? 'border-amber-400 text-amber-400' : 'border-transparent text-gray-500 hover:text-gray-300'"
      >{{ t.label }}</button>
    </div>
    <ScoreTable :rows="rows" :tab="tab" @added="load" />
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import ScoreTable from '../components/ScoreTable.vue'
import { getLeaderboard } from '../api'

const strategy = ref('trend')
const tab = ref('other')
const rows = ref([])

const strategies = [
  { value: 'short_term', label: '短线策略' },
  { value: 'trend', label: '趋势策略' },
  { value: 'value', label: '价值策略' },
]
const tabs = [
  { value: 'other', label: '其他股票' },
  { value: 'watchlist', label: '自选股' },
]

async function load() {
  rows.value = await getLeaderboard(strategy.value, tab.value)
}
watch([strategy, tab], load)
onMounted(load)
</script>
