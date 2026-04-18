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
      <span v-if="dataDate" class="text-gray-500 text-sm font-mono">{{ dataDate }}</span>
    </div>
    <ScoreTable :rows="rows" :tab="tab" @added="load" />
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import ScoreTable from '../components/ScoreTable.vue'
import { getLeaderboard } from '../api'

const tab = ref('other')
const rows = ref([])
const dataDate = ref('')

const tabs = [
  { value: 'other', label: '热门' },
  { value: 'watchlist', label: '自选股' },
]

async function load() {
  const res = await getLeaderboard(tab.value)
  dataDate.value = res.date || ''
  rows.value = res.stocks || res || []
}
watch(tab, load)
onMounted(load)
</script>
