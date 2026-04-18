<template>
  <div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-gray-800 text-gray-400">
          <th class="text-left py-2 px-3 w-12">排名</th>
          <th class="text-left py-2 px-3">股票</th>
          <th class="text-right py-2 px-3 cursor-pointer hover:text-white" @click="sort('total_score')">总分</th>
          <th class="text-right py-2 px-3 cursor-pointer hover:text-white" @click="sort('technical_score')">技术</th>
          <th class="text-right py-2 px-3 cursor-pointer hover:text-white" @click="sort('capital_score')">资金</th>
          <th class="text-right py-2 px-3 cursor-pointer hover:text-white" @click="sort('fundamental_score')">基本</th>
          <th class="text-right py-2 px-3 cursor-pointer hover:text-white" @click="sort('news_score')">消息</th>
          <th class="text-right py-2 px-3 cursor-pointer hover:text-white" @click="sort('heat_score')">热度</th>
          <th class="text-right py-2 px-3">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in sorted" :key="row.code" class="border-b border-gray-800/50 hover:bg-gray-900 transition-colors">
          <td class="py-2 px-3 text-gray-500 font-mono">{{ row.rank }}</td>
          <td class="py-2 px-3">
            <span class="font-medium">{{ row.name }}</span>
            <span class="ml-2 text-gray-500 font-mono text-xs">{{ row.code }}</span>
          </td>
          <td class="py-2 px-3 text-right font-mono font-semibold" :class="scoreColor(row.total_score)">{{ row.total_score }}</td>
          <td class="py-2 px-3 text-right font-mono text-gray-300">{{ row.technical_score }}</td>
          <td class="py-2 px-3 text-right font-mono text-gray-300">{{ row.capital_score }}</td>
          <td class="py-2 px-3 text-right font-mono text-gray-300">{{ row.fundamental_score }}</td>
          <td class="py-2 px-3 text-right font-mono text-gray-300">{{ row.news_score }}</td>
          <td class="py-2 px-3 text-right font-mono text-gray-300">{{ row.heat_score }}</td>
          <td class="py-2 px-3 text-right flex items-center justify-end gap-2">
            <router-link :to="'/stock/' + row.code" class="text-blue-400 hover:text-blue-300 text-xs">详情</router-link>
            <button v-if="tab === 'other'" @click="addToWatchlist(row)" class="text-amber-400 hover:text-amber-300 text-xs">+自选</button>
            <button v-if="tab === 'watchlist'" @click="removeFromWatchlist(row)" class="text-red-400 hover:text-red-300 text-xs">移除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!rows.length" class="text-center py-12 text-gray-600">暂无数据，请先触发采集</div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { addWatchlist, removeWatchlist } from '../api'

const props = defineProps({ rows: Array, tab: String })
const emit = defineEmits(['added'])
const sortKey = ref('total_score')
function sort(key) { sortKey.value = key }
const sorted = computed(() =>
  [...props.rows].sort((a, b) => b[sortKey.value] - a[sortKey.value]).map((r, i) => ({ ...r, rank: i + 1 }))
)
function scoreColor(score) {
  if (score >= 75) return 'text-green-400'
  if (score >= 50) return 'text-yellow-400'
  return 'text-red-400'
}
async function addToWatchlist(row) {
  await addWatchlist(row.code, row.name)
  emit('added')
}
async function removeFromWatchlist(row) {
  await removeWatchlist(row.code)
  emit('added')
}
</script>
