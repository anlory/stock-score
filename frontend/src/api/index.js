import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const getLeaderboard = (strategy, type) =>
  api.get('/scores/leaderboard', { params: { strategy, type } }).then(r => r.data)

export const getStockDetail = (code, strategy) =>
  api.get(`/scores/${code}`, { params: { strategy } }).then(r => r.data)

export const getStockHistory = (code, strategy, days) =>
  api.get(`/scores/${code}/history`, { params: { strategy, days } }).then(r => r.data)

export const getWatchlist = () =>
  api.get('/stocks/watchlist').then(r => r.data)

export const addWatchlist = (code, name) =>
  api.post('/stocks/watchlist', { code, name }).then(r => r.data)

export const removeWatchlist = (code) =>
  api.delete(`/stocks/watchlist/${code}`).then(r => r.data)

export const triggerCollect = () =>
  api.post('/trigger/collect').then(r => r.data)

export const getCollectStatus = () =>
  api.get('/trigger/status').then(r => r.data)
