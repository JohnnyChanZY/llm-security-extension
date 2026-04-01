// API客户端
import type { ApiResponse, LoginResponse, User, EventListResponse, Category, Model, Preference } from './types'

const API_BASE_URL = 'http://localhost:8000/api/v1'
const ADMIN_API_URL = 'http://localhost:8000/api/admin'

class ApiClient {
  private baseUrl: string
  private token: string | null = null
  private tokenLoaded: Promise<void>

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
    // 从storage加载token - 存储Promise以便等待
    this.tokenLoaded = this.loadToken()
  }

  private async loadToken() {
    const result = await chrome.storage.local.get(['token'])
    if (result.token) {
      this.token = result.token.access_token
    }
  }

  private async ensureTokenLoaded() {
    await this.tokenLoaded
  }

  setToken(token: string | null) {
    this.token = token
    if (token) {
      chrome.storage.local.set({ token: { access_token: token } })
    } else {
      chrome.storage.local.remove(['token'])
    }
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    // 确保token已加载
    await this.ensureTokenLoaded()

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    }

    if (this.token) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${this.token}`
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
    })

    return response.json()
  }

  // 认证API
  async login(email: string, password: string): Promise<ApiResponse<LoginResponse>> {
    const result = await this.request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    if (result.code === 0 && result.data) {
      // 设置内存中的token用于后续请求
      this.token = result.data.token.access_token
      // 注意：不在这里保存到storage，由stores.ts统一管理
    }
    return result
  }

  async register(email: string, password: string, nickname?: string): Promise<ApiResponse<User>> {
    return this.request<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, nickname }),
    })
  }

  async logout() {
    this.setToken(null)
    chrome.storage.local.remove(['user', 'token'])
  }

  async getProfile(): Promise<ApiResponse<User>> {
    return this.request<User>('/auth/profile')
  }

  async refreshToken(): Promise<ApiResponse<{ access_token: string; refresh_token: string }>> {
    const result = await chrome.storage.local.get(['token'])
    const refreshToken = result.token?.refresh_token
    if (!refreshToken) {
      return { code: 1002, message: '无刷新令牌', data: null }
    }
    return this.request('/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
  }

  // 事件API
  async getEvents(params: {
    page?: number
    page_size?: number
    category?: string
    model_id?: number
    severity?: string
    keyword?: string
  } = {}): Promise<ApiResponse<EventListResponse>> {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        searchParams.append(key, String(value))
      }
    })
    return this.request<EventListResponse>(`/events?${searchParams.toString()}`)
  }

  async getEventDetail(id: number, eventType: string = 'historical'): Promise<ApiResponse<any>> {
    return this.request(`/events/${id}?event_type=${eventType}`)
  }

  async getRecommendEvents(page: number = 1, category?: string): Promise<ApiResponse<EventListResponse>> {
    const params = new URLSearchParams()
    params.append('page', String(page))
    if (category) {
      params.append('category', category)
    }
    return this.request<EventListResponse>(`/events/recommend?${params.toString()}`)
  }

  async getSubscribedEvents(page: number = 1, category?: string): Promise<ApiResponse<EventListResponse>> {
    const params = new URLSearchParams()
    params.append('page', String(page))
    if (category) {
      params.append('category', category)
    }
    return this.request<EventListResponse>(`/events/subscribed?${params.toString()}`)
  }

  async getUnreadCount(): Promise<ApiResponse<{ count: number }>> {
    return this.request('/events/unread-count')
  }

  // 分类API
  async getCategories(): Promise<ApiResponse<Category[]>> {
    return this.request<Category[]>('/categories')
  }

  // 模型API
  async getModels(): Promise<ApiResponse<Model[]>> {
    return this.request<Model[]>('/models')
  }

  // 偏好API
  async getPreferences(): Promise<ApiResponse<Preference[]>> {
    return this.request<Preference[]>('/preferences')
  }

  async addPreference(data: {
    model_id?: number
    category_id?: number
    is_enabled?: boolean
  }): Promise<ApiResponse<Preference>> {
    return this.request<Preference>('/preferences', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async deletePreference(id: number): Promise<ApiResponse<void>> {
    return this.request<void>(`/preferences/${id}`, { method: 'DELETE' })
  }

  async updatePreference(id: number, is_enabled: boolean): Promise<ApiResponse<Preference>> {
    return this.request<Preference>(`/preferences/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ is_enabled }),
    })
  }
}

export const api = new ApiClient(API_BASE_URL)
export const adminApi = new ApiClient(ADMIN_API_URL)
