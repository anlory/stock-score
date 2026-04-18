<template>
  <div ref="el" style="width:320px;height:320px"></div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ scores: { type: Object, default: () => ({}) } })
const el = ref(null)
let chart = null

function render() {
  if (!chart) chart = echarts.init(el.value, 'dark')
  chart.setOption({
    backgroundColor: 'transparent',
    radar: {
      indicator: [
        { name: '技术面', max: 100 }, { name: '资金面', max: 100 },
        { name: '基本面', max: 100 }, { name: '消息面', max: 100 },
        { name: '市场热度', max: 100 },
      ],
      shape: 'polygon',
      axisName: { color: '#9CA3AF', fontSize: 12 },
      splitLine: { lineStyle: { color: '#374151' } },
      splitArea: { show: false },
      axisLine: { lineStyle: { color: '#374151' } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: [
          props.scores?.technical ?? 0, props.scores?.capital ?? 0,
          props.scores?.fundamental ?? 0, props.scores?.news ?? 0,
          props.scores?.heat ?? 0,
        ],
        areaStyle: { color: 'rgba(59,130,246,0.2)' },
        lineStyle: { color: '#3B82F6', width: 2 },
        itemStyle: { color: '#F59E0B' },
      }],
    }],
  })
}
onMounted(render)
watch(() => props.scores, render, { deep: true })
</script>
