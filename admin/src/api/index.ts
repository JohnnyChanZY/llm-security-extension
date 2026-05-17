// API客户端
import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('admin_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    const { data } = response
    if (data.code !== 0) {
      ElMessage.error(data.message || '请求失败')
      return Promise.reject(data)
    }
    return data
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('admin_token')
      window.location.href = '/login'
    }
    ElMessage.error(error.response?.data?.message || '请求失败')
    return Promise.reject(error)
  }
)

// 认证API
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/v1/auth/login', { email, password }),
  getProfile: () => api.get('/v1/auth/profile')
}

// 系统配置API
export const configApi = {
  getAll: () => api.get('/admin/configs'),
  getLLM: () => api.get('/admin/configs/llm'),
  update: (key: string, value: string) =>
    api.put(`/admin/configs/${key}`, { config_value: value })
}

// RSS数据源API
export const rssApi = {
  getAll: () => api.get('/admin/rss-sources'),
  create: (data: any) => api.post('/admin/rss-sources', data),
  update: (id: number, data: any) => api.put(`/admin/rss-sources/${id}`, data),
  delete: (id: number) => api.delete(`/admin/rss-sources/${id}`),
  validate: (id: number) => api.post(`/admin/rss-sources/${id}/validate`),
  crawl: (id: number) => api.post(`/admin/rss-sources/${id}/crawl`),
  crawlAll: () => api.post('/admin/rss-sources/actions/crawl-all')
}

// 模型管理API
export const modelApi = {
  getAll: (includeDisabled = true) =>
    api.get(`/admin/models?include_disabled=${includeDisabled}`),
  create: (data: any) => api.post('/admin/models', data),
  update: (id: number, data: any) => api.put(`/admin/models/${id}`, data),
  delete: (id: number) => api.delete(`/admin/models/${id}`)
}

// 评级API
export const ratingApi = {
  trigger: (params?: any) => api.post('/admin/rating/trigger', params, { timeout: 300000 }),
  getStatus: () => api.get('/admin/rating/status'),
  // 批量操作（后台任务模式）
  batchOperations: (data: { event_ids: number[], event_type: string, operations: string[] }) =>
    api.post('/admin/rating/batch-operations', data),
  // 各类操作（后台任务模式）
  rate: (data: { event_ids: number[], event_type: string }) =>
    api.post('/admin/rating/rate', { ...data, mode: 'rate' }),
  classify: (data: { event_ids: number[], event_type: string }) =>
    api.post('/admin/rating/classify', data),
  rateAndClassify: (data: { event_ids: number[], event_type: string }) =>
    api.post('/admin/rating/rate-and-classify', data),
  checkSecurity: (data: { event_ids: number[], event_type: string }) =>
    api.post('/admin/rating/check-security', data),
  stop: () => api.post('/admin/rating/stop')
}

// LLM事件管理API
export const llmEventsApi = {
  // 获取事件列表
  getEvents: (params: any) => api.get('/admin/events', { params }),
  // 获取事件统计
  getStats: () => api.get('/admin/events/stats'),
  // 复用 ratingApi 的方法
  rate: ratingApi.rate,
  classify: ratingApi.classify,
  rateAndClassify: ratingApi.rateAndClassify,
  checkSecurity: ratingApi.checkSecurity,
  batchOperations: ratingApi.batchOperations,
  // 删除单个事件
  deleteEvent: (eventId: number, eventTable: string) =>
    api.delete(`/admin/events/${eventTable}/${eventId}`),
  // 批量删除
  batchDelete: (eventIds: number[], eventTable: string) =>
    api.post('/admin/events/batch-delete', { event_ids: eventIds, event_table: eventTable }),
}

// 数据同步API
export const syncApi = {
  syncNVD: (days: number = 30) => api.post(`/admin/sync/nvd?days=${days}`),
  syncAIID: () => api.post('/admin/sync/aiid'),
  syncAIVD: () => api.post('/admin/sync/aivd')
}

// 仪表盘API
export const dashboardApi = {
  getStats: () => api.get('/admin/dashboard/stats')
}

// 操作日志API
export const logsApi = {
  getAll: (params: { page?: number; page_size?: number }) =>
    api.get('/admin/logs', { params })
}

export default api
