// Pinia状态管理
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, Token, Category, Model, Preference, Event } from '../shared/types'
import { api } from '../shared/api'
import { storage } from '../shared/storage'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<Token | null>(null)
  const isLoggedIn = computed(() => !!user.value && !!token.value)

  async function init() {
    user.value = await storage.getUser()
    token.value = await storage.getToken()
  }

  async function login(email: string, password: string) {
    const result = await api.login(email, password)
    if (result.code === 0 && result.data) {
      user.value = result.data.user
      token.value = result.data.token
      await storage.setUser(result.data.user)
      await storage.setToken(result.data.token)

      // 通知background连接WebSocket
      chrome.runtime.sendMessage({
        type: 'LOGIN',
        data: {
          token: result.data.token.access_token,
          user: result.data.user
        }
      })
    }
    return result
  }

  async function register(email: string, password: string, nickname?: string) {
    return await api.register(email, password, nickname)
  }

  async function logout() {
    await api.logout()
    user.value = null
    token.value = null
    chrome.runtime.sendMessage({ type: 'LOGOUT' })
  }

  return {
    user,
    token,
    isLoggedIn,
    init,
    login,
    register,
    logout
  }
})

export const useEventStore = defineStore('event', () => {
  const events = ref<Event[]>([])
  const total = ref(0)
  const page = ref(1)
  const loading = ref(false)
  const unreadCount = ref(0)

  async function fetchEvents(params: {
    page?: number
    category?: string
    model_id?: number
    severity?: string
    keyword?: string
  } = {}) {
    loading.value = true
    try {
      const result = await api.getEvents({ page_size: 20, ...params })
      if (result.code === 0 && result.data) {
        events.value = result.data.items
        total.value = result.data.total
        page.value = result.data.page
      }
    } finally {
      loading.value = false
    }
  }

  async function fetchRecommendEvents(p: number = 1, category?: string) {
    loading.value = true
    try {
      const result = await api.getRecommendEvents(p, category)
      if (result.code === 0 && result.data) {
        events.value = result.data.items
        total.value = result.data.total
        page.value = result.data.page
      }
    } finally {
      loading.value = false
    }
  }

  async function fetchSubscribedEvents(p: number = 1, category?: string) {
    loading.value = true
    try {
      const result = await api.getSubscribedEvents(p, category)
      if (result.code === 0 && result.data) {
        events.value = result.data.items
        total.value = result.data.total
        page.value = result.data.page
      }
    } finally {
      loading.value = false
    }
  }

  async function fetchUnreadCount() {
    const result = await api.getUnreadCount()
    if (result.code === 0 && result.data) {
      unreadCount.value = result.data.count
    }
  }

  return {
    events,
    total,
    page,
    loading,
    unreadCount,
    fetchEvents,
    fetchRecommendEvents,
    fetchSubscribedEvents,
    fetchUnreadCount
  }
})

export const useCategoryStore = defineStore('category', () => {
  const categories = ref<Category[]>([])
  const loading = ref(false)

  async function fetchCategories() {
    loading.value = true
    try {
      const result = await api.getCategories()
      if (result.code === 0 && result.data) {
        categories.value = result.data
      }
    } finally {
      loading.value = false
    }
  }

  return {
    categories,
    loading,
    fetchCategories
  }
})

export const useModelStore = defineStore('model', () => {
  const models = ref<Model[]>([])
  const loading = ref(false)

  async function fetchModels() {
    loading.value = true
    try {
      const result = await api.getModels()
      if (result.code === 0 && result.data) {
        models.value = result.data
      }
    } finally {
      loading.value = false
    }
  }

  return {
    models,
    loading,
    fetchModels
  }
})

export const usePreferenceStore = defineStore('preference', () => {
  const preferences = ref<Preference[]>([])
  const loading = ref(false)

  async function fetchPreferences() {
    loading.value = true
    try {
      const result = await api.getPreferences()
      if (result.code === 0 && result.data) {
        preferences.value = result.data
      }
    } finally {
      loading.value = false
    }
  }

  async function addPreference(data: { model_id?: number; category_id?: number }) {
    return await api.addPreference(data)
  }

  async function deletePreference(id: number) {
    return await api.deletePreference(id)
  }

  async function updatePreference(id: number, is_enabled: boolean) {
    return await api.updatePreference(id, is_enabled)
  }

  return {
    preferences,
    loading,
    fetchPreferences,
    addPreference,
    deletePreference,
    updatePreference
  }
})
