<template>
  <div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-gray-800 text-gray-500">
          <th class="text-center py-3 px-3 w-12">#</th>
          <th class="text-left py-3 px-3">股票</th>
          <th class="text-center py-3 px-3 w-20">总分</th>
          <th class="text-center py-3 px-3 w-16">技术</th>
          <th class="text-center py-3 px-3 w-16">资金</th>
          <th class="text-center py-3 px-3 w-16">热度</th>
          <th class="text-center py-3 px-3 w-20">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, idx) in rows" :key="row.code"
          class="border-b border-gray-800/50 hover:bg-gray-900 transition-colors cursor-pointer"
          @dblclick="$router.push('/stock/' + row.code)">
          <td class="py-3 px-3 text-center text-gray-600 font-mono text-xs">{{ idx + 1 }}</td>
          <td class="py-3 px-3">
            <span class="font-medium text-gray-200">{{ row.name }}</span>
            <span class="ml-2 text-gray-600 font-mono text-xs">{{ row.code }}</span>
          </td>
          <td class="py-3 px-3 text-center font-mono font-semibold" :class="scoreColor(row.total_score)">{{ row.total_score != null ? Math.round(row.total_score) : '-' }}</td>
          <td class="py-3 px-3 text-center font-mono text-gray-400 text-xs">{{ row.technical_score != null ? Math.round(row.technical_score) : '-' }}</td>
          <td class="py-3 px-3 text-center font-mono text-gray-400 text-xs">{{ row.capital_score != null ? Math.round(row.capital_score) : '-' }}</td>
          <td class="py-3 px-3 text-center font-mono text-gray-400 text-xs">{{ row.heat_score != null ? Math.round(row.heat_score) : '-' }}</td>
          <td class="py-3 px-3 text-center">
            <button v-if="!row.is_watchlist" @click.stop="add(row)" class="text-amber-400 hover:text-amber-300 text-xs">+自选</button>
            <button v-else @click.stop="remove(row)" class="text-red-400 hover:text-red-300 text-xs">移除</button>
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

function scoreColor(s) {
  if (!s) return 'text-gray-600'
  if (s >= 75) return 'text-green-400'
  if (s >= 50) return 'text-yellow-400'
  return 'text-red-400'
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
