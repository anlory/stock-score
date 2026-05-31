<template>
  <div ref="el" class="trend-chart"></div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ records: { type: Array, default: () => [] } })
const el = ref(null)
let chart = null

const LINES = [
  { key: 'total_score', name: '总分', color: '#f59e0b', width: 2.5 },
  { key: 'technical_score', name: '技术面', color: '#60a5fa', width: 1.5 },
  { key: 'capital_score', name: '资金面', color: '#34d399', width: 1.5 },
  { key: 'fundamental_score', name: '基本面', color: '#a78bfa', width: 1.5 },
  { key: 'news_score', name: '消息面', color: '#fb923c', width: 1.5 },
  { key: 'heat_score', name: '市场热度', color: '#f472b6', width: 1.5 },
]

function render() {
  if (!chart) chart = echarts.init(el.value)
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(10, 14, 26, 0.9)',
      borderColor: 'rgba(148, 163, 184, 0.1)',
      borderWidth: 1,
      textStyle: {
        color: 'rgba(241, 245, 249, 0.8)',
        fontSize: 12,
        fontFamily: 'JetBrains Mono',
      },
    },
    legend: {
      textStyle: {
        color: 'rgba(148, 163, 184, 0.4)',
        fontSize: 11,
        fontFamily: 'DM Sans',
      },
      top: 0,
      itemGap: 16,
      icon: 'roundRect',
      itemWidth: 12,
      itemHeight: 3,
    },
    grid: {
      top: 36,
      bottom: 36,
      left: 44,
      right: 16,
    },
    xAxis: {
      type: 'category',
      data: props.records.map(r => r.date),
      axisLabel: {
        color: 'rgba(148, 163, 184, 0.25)',
        fontSize: 10,
        fontFamily: 'JetBrains Mono',
      },
      axisLine: {
        lineStyle: { color: 'rgba(148, 163, 184, 0.06)' },
      },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: {
        color: 'rgba(148, 163, 184, 0.2)',
        fontSize: 10,
        fontFamily: 'JetBrains Mono',
      },
      splitLine: {
        lineStyle: { color: 'rgba(148, 163, 184, 0.04)' },
      },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: LINES.map(l => ({
      name: l.name,
      type: 'line',
      smooth: 0.3,
      data: props.records.map(r => r[l.key]),
      lineStyle: {
        color: l.color,
        width: l.width,
      },
      itemStyle: {
        color: l.color,
      },
      showSymbol: props.records.length < 15,
      symbolSize: 4,
      emphasis: {
        lineStyle: { width: l.width + 1 },
      },
      animationDuration: 1000,
      animationEasing: 'cubicOut',
    })),
  })
}
onMounted(render)
watch(() => props.records, render, { deep: true })
</script>

<style scoped>
.trend-chart {
  width: 100%;
  height: 400px;
}
</style>
