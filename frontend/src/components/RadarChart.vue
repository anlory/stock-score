<template>
  <div ref="el" class="radar-chart"></div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ scores: { type: Object, default: () => ({}) } })
const el = ref(null)
let chart = null

function render() {
  if (!chart) chart = echarts.init(el.value)
  chart.setOption({
    backgroundColor: 'transparent',
    radar: {
      indicator: [
        { name: '技术面', max: 100 },
        { name: '资金面', max: 100 },
        { name: '市场热度', max: 100 },
      ],
      shape: 'polygon',
      radius: '68%',
      center: ['50%', '52%'],
      axisName: {
        color: 'rgba(148, 163, 184, 0.45)',
        fontSize: 11,
        fontFamily: 'DM Sans',
        fontWeight: 500,
      },
      splitNumber: 4,
      splitLine: {
        lineStyle: {
          color: 'rgba(148, 163, 184, 0.06)',
        },
      },
      splitArea: {
        show: true,
        areaStyle: {
          color: [
            'rgba(148, 163, 184, 0.01)',
            'rgba(148, 163, 184, 0.02)',
            'rgba(148, 163, 184, 0.01)',
            'rgba(148, 163, 184, 0.02)',
          ],
        },
      },
      axisLine: {
        lineStyle: {
          color: 'rgba(148, 163, 184, 0.06)',
        },
      },
    },
    series: [{
      type: 'radar',
      data: [{
        value: [
          props.scores?.technical ?? 0,
          props.scores?.capital ?? 0,
          props.scores?.heat ?? 0,
        ],
        areaStyle: {
          color: new echarts.graphic.RadialGradient(0.5, 0.5, 1, [
            { offset: 0, color: 'rgba(245, 158, 11, 0.15)' },
            { offset: 1, color: 'rgba(245, 158, 11, 0.02)' },
          ]),
        },
        lineStyle: {
          color: 'rgba(245, 158, 11, 0.6)',
          width: 2,
        },
        itemStyle: {
          color: '#f59e0b',
          borderColor: 'rgba(245, 158, 11, 0.3)',
          borderWidth: 2,
        },
        symbol: 'circle',
        symbolSize: 6,
      }],
      animationDuration: 800,
      animationEasing: 'cubicOut',
    }],
  })
}
onMounted(render)
watch(() => props.scores, render, { deep: true })
</script>

<style scoped>
.radar-chart {
  width: 300px;
  height: 300px;
  flex-shrink: 0;
}
</style>
