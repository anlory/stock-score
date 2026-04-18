<template>
  <div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-gray-800 text-gray-400">
          <th class="text-center py-3 px-5 w-16">排名</th>
          <th class="text-center py-3 px-5 w-40">股票</th>
          <th class="text-center py-3 px-5 w-20 cursor-pointer hover:text-white" @click="sort('short_score')">短线</th>
          <th class="text-center py-3 px-5 w-20 cursor-pointer hover:text-white" @click="sort('trend_score')">趋势</th>
          <th class="text-center py-3 px-5 w-20 cursor-pointer hover:text-white" @click="sort('technical_score')">技术</th>
          <th class="text-center py-3 px-5 w-20 cursor-pointer hover:text-white" @click="sort('capital_score')">资金</th>
          <th class="text-center py-3 px-5 w-20 cursor-pointer hover:text-white" @click="sort('fundamental_score')">基本</th>
          <th class="text-center py-3 px-5 w-20 cursor-pointer hover:text-white" @click="sort('news_score')">消息</th>
          <th class="text-center py-3 px-5 w-20 cursor-pointer hover:text-white" @click="sort('heat_score')">热度</th>
          <th class="text-center py-3 px-5 w-24">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in sorted" :key="row.code"
          class="border-b border-gray-800/50 hover:bg-gray-900 transition-colors cursor-pointer"
          @dblclick="$router.push('/stock/' + row.code)">
          <td class="py-3 px-5 text-center text-gray-500 font-mono">{{ row.rank }}</td>
          <td class="py-3 px-5 text-center">
            <span class="font-medium">{{ row.name }}</span>
            <span class="ml-2 text-gray-500 font-mono text-xs">{{ row.code }}</span>
          </td>
          <td class="py-3 px-5 text-center font-mono font-semibold" :class="scoreColor(row.short_score)">{{ row.short_score ?? '-' }}</td>
          <td class="py-3 px-5 text-center font-mono font-semibold" :class="scoreColor(row.trend_score)">{{ row.trend_score ?? '-' }}</td>
          <td class="py-3 px-5 text-center font-mono text-gray-300">{{ row.technical_score ?? '-' }}</td>
          <td class="py-3 px-5 text-center font-mono text-gray-300">{{ row.capital_score ?? '-' }}</td>
          <td class="py-3 px-5 text-center font-mono text-gray-300">{{ row.fundamental_score ?? '-' }}</td>
          <td class="py-3 px-5 text-center font-mono text-gray-300">{{ row.news_score ?? '-' }}</td>
          <td class="py-3 px-5 text-center font-mono text-gray-300">{{ row.heat_score ?? '-' }}</td>
          <td class="py-3 px-5 text-center">
            <button v-if="tab === 'other' && !row.is_watchlist" @click.stop="addToWatchlist(row)" class="text-amber-400 hover:text-amber-300 text-xs">+自选</button>
            <span v-if="tab === 'other' && row.is_watchlist" class="text-gray-600 text-xs">已加</span>
            <button v-if="tab === 'watchlist'" @click.stop="removeFromWatchlist(row)" class="text-red-400 hover:text-red-300 text-xs">移除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!rows.length" class="text-center py-12 text-gray-600">暂无数据，请先触发采集</div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { addWatchlist, removeWatchlist } from '../api'

const router = useRouter()
const props = defineProps({ rows: Array, tab: String })
const emit = defineEmits(['added'])
const sortKey = ref('trend_score')
function sort(key) { sortKey.value = key }
const sorted = computed(() =>
  [...props.rows].sort((a, b) => (b[sortKey.value] ?? 0) - (a[sortKey.value] ?? 0)).map((r, i) => ({ ...r, rank: i + 1 }))
)
function scoreColor(score) {
  if (!score) return 'text-gray-500'
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
