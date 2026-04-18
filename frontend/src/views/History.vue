<template>
  <div class="p-6 max-w-5xl mx-auto">
    <h1 class="text-xl font-bold mb-6">历史趋势</h1>
    <div class="flex flex-wrap gap-3 mb-6">
      <input v-model="code" @keyup.enter="load" placeholder="输入股票代码，按 Enter"
        class="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm w-40 font-mono focus:outline-none focus:border-blue-500" />
      <select v-model="strategy" @change="load"
        class="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm">
        <option value="short_term">短线策略</option>
        <option value="trend">趋势策略</option>
        <option value="value">价值策略</option>
      </select>
      <div class="flex gap-2">
        <button v-for="d in dayOpts" :key="d" @click="days = d; load()"
          class="px-3 py-1.5 rounded text-sm transition-colors"
          :class="days === d ? 'bg-blue-800 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'"
        >近{{ d }}天</button>
      </div>
    </div>
    <div v-if="!records.length" class="text-center text-gray-600 py-20">请输入股票代码查询</div>
    <TrendChart v-else :records="records" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import TrendChart from '../components/TrendChart.vue'
import { getStockHistory } from '../api'

const code = ref('')
const strategy = ref('trend')
const days = ref(30)
const records = ref([])
const dayOpts = [7, 30, 90]

async function load() {
  if (!code.value) return
  records.value = await getStockHistory(code.value, strategy.value, days.value)
}
</script>
