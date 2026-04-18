<template>
  <div ref="el" style="width:100%;height:400px"></div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ data: { type: Array, default: () => [] } })
const el = ref(null)
let chart = null

function render() {
  if (!chart) chart = echarts.init(el.value, 'dark')
  if (!props.data.length) return

  const dates = props.data.map(d => d.date)
  const ohlc = props.data.map(d => [d.open, d.close, d.low, d.high])
  const volumes = props.data.map(d => d.volume)

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { show: false },
    grid: [
      { left: 50, right: 20, top: 10, bottom: '32%' },
      { left: 50, right: 20, top: '74%', bottom: 30 },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLabel: { show: false }, axisTick: { show: false } },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { color: '#6B7280', fontSize: 10 } },
    ],
    yAxis: [
      { scale: true, gridIndex: 0, axisLabel: { color: '#6B7280' }, splitLine: { lineStyle: { color: '#1F2937' } } },
      { scale: true, gridIndex: 1, axisLabel: { color: '#6B7280', formatter: v => v >= 1e6 ? (v/1e6).toFixed(0)+'M' : v >= 1e3 ? (v/1e3).toFixed(0)+'K' : v }, splitLine: { show: false } },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: '#EF4444',
          color0: '#22C55E',
          borderColor: '#EF4444',
          borderColor0: '#22C55E',
        },
      },
      {
        name: '成交量',
        type: 'bar',
        data: volumes,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: {
          color: function(params) {
            const d = props.data[params.dataIndex]
            return d && d.close >= d.open ? '#EF4444' : '#22C55E'
          },
        },
      },
    ],
  })
}

onMounted(render)
watch(() => props.data, render, { deep: true })
</script>
