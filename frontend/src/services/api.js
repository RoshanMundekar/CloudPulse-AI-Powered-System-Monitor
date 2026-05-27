/**
 * API Service — all HTTP calls to the FastAPI backend.
 * Vite proxy routes /api/* → http://localhost:8000
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
})

// Global response interceptor — log errors in dev
api.interceptors.response.use(
  res => res,
  err => {
    if (import.meta.env.DEV) {
      console.warn(`[API] ${err.config?.method?.toUpperCase()} ${err.config?.url}`,
        err.response?.status, err.response?.data)
    }
    return Promise.reject(err)
  }
)

// ── Metrics ──────────────────────────────────────────────────────────────────
export const getLatestMetric   = ()               => api.get('/metrics/latest')
export const getMetricHistory  = (hours = 1, limit = 500) =>
  api.get(`/metrics/history?hours=${hours}&limit=${limit}`)
export const getMetricBuckets  = (hours = 24)     => api.get(`/metrics/buckets?hours=${hours}`)
export const getSparkline      = ()               => api.get('/metrics/sparkline')
export const getMetricAverages = (hours = 24)     => api.get(`/metrics/averages?hours=${hours}`)
export const getMetricById     = (id)             => api.get(`/metrics/${id}`)

// ── Alerts ───────────────────────────────────────────────────────────────────
export const getAlerts         = (unreadOnly = false, limit = 50) =>
  api.get(`/alerts/?unread_only=${unreadOnly}&limit=${limit}`)
export const getAlertCount     = ()              => api.get('/alerts/count')
export const updateAlert       = (id, data)      => api.patch(`/alerts/${id}`, data)
export const markAllAlertsRead = ()              => api.post('/alerts/mark-all-read')

// ── Anomalies ────────────────────────────────────────────────────────────────
export const getAnomalies      = (hours = 24)    => api.get(`/anomalies/?hours=${hours}`)
export const getAnomalyCount   = (hours = 1)     => api.get(`/anomalies/count?hours=${hours}`)
export const resolveAnomaly    = (id)            => api.patch(`/anomalies/${id}`, { is_resolved: true })

// ── System ───────────────────────────────────────────────────────────────────
export const getSystemInfo     = ()              => api.get('/system/info')

export default api
