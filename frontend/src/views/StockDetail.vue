<template>
  <div class="p-6 max-w-5xl mx-auto">
    <button @click="$router.back()" class="text-gray-400 hover:text-white mb-4 text-sm">← 返回</button>
    <div v-if="!data" class="text-gray-600 text-center py-20">加载中...</div>
    <template v-else>
      <div class="flex items-center gap-4 mb-6">
        <h1 class="text-2xl font-bold">{{ data.name }}</h1>
        <span class="font-mono text-gray-400">{{ data.code }}</span>
        <span class="ml-auto bg-blue-900/40 text-blue-300 border border-blue-800/40 px-3 py-1 rounded-full font-mono font-bold text-lg">
          {{ data.scores?.total ?? '-' }} 分
        </span>
      </div>
      <div class="flex gap-2 mb-6">
        <button v-for="s in strategies" :key="s.value" @click="strategy = s.value"
          class="px-3 py-1 rounded text-sm transition-colors"
          :class="strategy === s.value ? 'bg-blue-800 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'"
        >{{ s.label }}</button>
      </div>
      <div class="flex gap-6 flex-wrap mb-6">
        <RadarChart :scores="data.scores" />
        <div class="flex-1 grid grid-cols-1 gap-3 min-w-[260px]">
          <div v-for="dim in dimensions" :key="dim.key"
            class="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 flex items-center justify-between">
            <span class="text-gray-400 text-sm">{{ dim.label }}</span>
            <span class="font-mono font-semibold text-lg" :class="scoreColor(data.scores?.[dim.key])">
              {{ data.scores?.[dim.key] ?? '-' }}
            </span>
          </div>
        </div>
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h2 class="text-sm text-gray-400 mb-3 font-semibold">原始指标数据</h2>
        <div class="grid grid-cols-3 gap-2 text-xs font-mono">
          <div v-for="(val, key) in displayRaw" :key="key" class="flex justify-between border-b border-gray-800/50 py-1">
            <span class="text-gray-500">{{ key }}</span>
            <span class="text-gray-200">{{ val ?? '-' }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import RadarChart from '../components/RadarChart.vue'
import { getStockDetail } from '../api'

const route = useRoute()
const strategy = ref('trend')
const data = ref(null)

const strategies = [
  { value: 'short_term', label: '短线' },
  { value: 'trend', label: '趋势' },
  { value: 'value', label: '价值' },
]
const dimensions = [
  { key: 'technical', label: '技术面' },
  { key: 'capital', label: '资金面' },
  { key: 'fundamental', label: '基本面' },
  { key: 'news', label: '消息面' },
  { key: 'heat', label: '市场热度' },
]
const SKIP = new Set(['code', 'date', '_sa_instance_state'])
const displayRaw = computed(() => {
  if (!data.value?.raw) return {}
  return Object.fromEntries(Object.entries(data.value.raw).filter(([k]) => !SKIP.has(k)))
})
function scoreColor(s) {
  if (!s) return 'text-gray-400'
  if (s >= 75) return 'text-green-400'
  if (s >= 50) return 'text-yellow-400'
  return 'text-red-400'
}
async function load() {
  data.value = await getStockDetail(route.params.code, strategy.value)
}
watch(strategy, load)
onMounted(load)
</script>
