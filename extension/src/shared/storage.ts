// 本地存储管理
import type { User, Token } from './types'

const STORAGE_KEYS = {
  USER: 'user',
  TOKEN: 'token',
  PREFERENCES: 'preferences',
}

export const storage = {
  async getUser(): Promise<User | null> {
    const result = await chrome.storage.local.get([STORAGE_KEYS.USER])
    return result[STORAGE_KEYS.USER] || null
  },

  async setUser(user: User): Promise<void> {
    await chrome.storage.local.set({ [STORAGE_KEYS.USER]: user })
  },

  async getToken(): Promise<Token | null> {
    const result = await chrome.storage.local.get([STORAGE_KEYS.TOKEN])
    return result[STORAGE_KEYS.TOKEN] || null
  },

  async setToken(token: Token): Promise<void> {
    await chrome.storage.local.set({ [STORAGE_KEYS.TOKEN]: token })
  },

  async clearAuth(): Promise<void> {
    await chrome.storage.local.remove([STORAGE_KEYS.USER, STORAGE_KEYS.TOKEN])
  },

  async getPreferences(): Promise<any[]> {
    const result = await chrome.storage.local.get([STORAGE_KEYS.PREFERENCES])
    return result[STORAGE_KEYS.PREFERENCES] || []
  },

  async setPreferences(preferences: any[]): Promise<void> {
    await chrome.storage.local.set({ [STORAGE_KEYS.PREFERENCES]: preferences })
  },

  async isLoggedIn(): Promise<boolean> {
    const token = await this.getToken()
    return !!token && !!token.access_token
  },
}
