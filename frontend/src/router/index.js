import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import StockDetail from '../views/StockDetail.vue'

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: Dashboard },
    { path: '/watchlist', component: Dashboard },
    { path: '/hk', component: Dashboard },
    { path: '/stock/:code', component: StockDetail },
  ],
})
