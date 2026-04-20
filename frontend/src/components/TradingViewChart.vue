<template>
  <div class="tradingview-widget-container" ref="container">
    <div class="tradingview-widget-container__widget"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'

const props = defineProps({ code: String })
const container = ref(null)

function getSymbol(code) {
  if (code.startsWith('6') || code.startsWith('9')) return `SSE:${code}`
  if (code.startsWith('0') || code.startsWith('3')) return `SZSE:${code}`
  return `SSE:${code}`
}

function loadWidget() {
  if (!container.value) return
  const widgetDiv = container.value.querySelector('.tradingview-widget-container__widget')
  if (!widgetDiv) return
  widgetDiv.innerHTML = ''
  // Remove old scripts
  container.value.querySelectorAll('script').forEach(s => s.remove())

  const script = document.createElement('script')
  script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js'
  script.async = true
  script.innerHTML = JSON.stringify({
    width: "100%",
    height: 500,
    symbol: getSymbol(props.code),
    interval: "D",
    timezone: "Asia/Shanghai",
    theme: "dark",
    style: "1",
    locale: "zh_CN",
    allow_symbol_change: true,
    hide_top_toolbar: false,
    hide_legend: false,
    save_image: false,
    support_host: "https://www.tradingview.com",
  })
  container.value.appendChild(script)
}

onMounted(loadWidget)
watch(() => props.code, loadWidget)
</script>
