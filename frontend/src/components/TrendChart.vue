<template>
  <div ref="el" style="width:100%;height:400px"></div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ records: { type: Array, default: () => [] } })
const el = ref(null)
let chart = null

const LINES = [
  { key: 'total_score', name: '总分', color: '#F59E0B', width: 3 },
  { key: 'technical_score', name: '技术面', color: '#3B82F6' },
  { key: 'capital_score', name: '资金面', color: '#10B981' },
  { key: 'fundamental_score', name: '基本面', color: '#8B5CF6' },
  { key: 'news_score', name: '消息面', color: '#F97316' },
  { key: 'heat_score', name: '市场热度', color: '#EC4899' },
]

function render() {
  if (!chart) chart = echarts.init(el.value, 'dark')
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { textStyle: { color: '#9CA3AF' }, top: 0 },
    grid: { top: 40, bottom: 40, left: 40, right: 20 },
    xAxis: { type: 'category', data: props.records.map(r => r.date), axisLabel: { color: '#6B7280' } },
    yAxis: { type: 'value', min: 0, max: 100, axisLabel: { color: '#6B7280' } },
    series: LINES.map(l => ({
      name: l.name, type: 'line', smooth: true,
      data: props.records.map(r => r[l.key]),
      lineStyle: { color: l.color, width: l.width || 1.5 },
      itemStyle: { color: l.color },
      showSymbol: props.records.length < 15,
    })),
  })
}
onMounted(render)
watch(() => props.records, render, { deep: true })
</script>
