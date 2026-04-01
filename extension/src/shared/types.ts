// 类型定义

export interface User {
  id: number
  email: string
  nickname: string | null
  is_admin: boolean
  is_active: boolean
  created_at: string
}

export interface Token {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface LoginResponse {
  user: User
  token: Token
}

export interface Category {
  id: number
  code: string
  name: string
  description: string | null
}

export interface Model {
  id: number
  name: string
  vendor: string | null
  description: string | null
}

export interface Event {
  id: number
  title: string
  description: string | null
  source_type: string | null
  source_name: string | null
  original_url: string | null
  published_at: string | null
  category: Category | null
  cve_id: string | null
  severity: 'low' | 'medium' | 'high' | 'critical' | null
  severity_source: string | null
  affected_models: Model[]
  created_at: string
}

export interface EventListResponse {
  items: Event[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface Preference {
  id: number
  user_id: number
  model_id: number | null
  category_id: number | null
  is_enabled: boolean
  model_name: string | null
  category_name: string | null
}

export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T | null
}

export interface SystemConfig {
  llm_classify_enabled: boolean
  llm_rating_enabled: boolean
  llm_batch_size: number
}
