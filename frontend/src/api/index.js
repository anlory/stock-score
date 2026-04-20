import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const getLeaderboard = (type) =>
  api.get('/scores/leaderboard', { params: { type } }).then(r => r.data)

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

export const getKline = (code, days = 60) =>
  api.get(`/scores/kline/${code}`, { params: { days } }).then(r => r.data)

export const getAnalysis = (code) =>
  api.get(`/analysis/${code}`).then(r => r.data)

export const getStockProfile = (code) =>
  api.get(`/stocks/${code}/profile`).then(r => r.data)
