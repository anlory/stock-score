import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import StockDetail from '../views/StockDetail.vue'
import History from '../views/History.vue'

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: Dashboard },
    { path: '/stock/:code', component: StockDetail },
    { path: '/history', component: History },
  ],
})
