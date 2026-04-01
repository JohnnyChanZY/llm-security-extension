<template>
  <div class="popup-container">
    <!-- 加载中 -->
    <div v-if="initializing" class="loading-section">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
    </div>

    <!-- 未登录状态 -->
    <div v-else-if="!authStore.isLoggedIn" class="login-section">
      <h2>LLM安全事件推送</h2>
      <el-form :model="loginForm" @submit.prevent="handleLogin">
        <el-form-item>
          <el-input
            v-model="loginForm.email"
            placeholder="邮箱"
            prefix-icon="User"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="密码"
            prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" block>
          登录
        </el-button>
      </el-form>
    </div>

    <!-- 已登录状态 -->
    <div v-else class="logged-in-section">
      <!-- 用户信息 -->
      <div class="user-info">
        <span class="nickname">{{ authStore.user?.nickname || authStore.user?.email }}</span>
        <el-button text type="danger" size="small" @click="handleLogout">
          登出
        </el-button>
      </div>

      <!-- 未读数量 -->
      <div class="unread-section" v-if="unreadCount > 0">
        <span class="unread-badge">{{ unreadCount }} 条未读</span>
      </div>

      <!-- 最近事件 -->
      <div class="recent-events">
        <h3>最近事件</h3>
        <div v-if="eventStore.loading" class="loading">
          <el-skeleton :rows="3" animated />
        </div>
        <div v-else-if="eventStore.events.length === 0" class="empty">
          暂无新事件
        </div>
        <div v-else class="event-list">
          <div
            v-for="event in recentEvents"
            :key="event.id"
            class="event-item"
            @click="openSidePanel(event)"
          >
            <div class="event-title">
              <el-tag
                :type="severityType(event.severity)"
                size="small"
                effect="dark"
              >
                {{ severityText(event.severity) }}
              </el-tag>
              <span class="title-text">{{ truncate(event.title, 30) }}</span>
            </div>
            <div class="event-meta">
              <span class="source">{{ event.source_name }}</span>
              <span class="time">{{ formatTime(event.published_at) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 打开侧边栏按钮 -->
      <el-button type="primary" block @click="openSidePanel()">
        <el-icon><Expand /></el-icon>
        打开侧边栏
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore, useEventStore } from '../shared/stores'
import { Expand, Loading } from '@element-plus/icons-vue'

const authStore = useAuthStore()
const eventStore = useEventStore()

const initializing = ref(true)
const loginForm = ref({
  email: '',
  password: ''
})
const loading = ref(false)
const unreadCount = ref(0)

const recentEvents = computed(() => eventStore.events.slice(0, 5))

onMounted(async () => {
  await authStore.init()
  initializing.value = false
  if (authStore.isLoggedIn) {
    await eventStore.fetchRecommendEvents(1)
    await eventStore.fetchUnreadCount()
    unreadCount.value = eventStore.unreadCount
  }
})

async function handleLogin() {
  loading.value = true
  try {
    const result = await authStore.login(loginForm.value.email, loginForm.value.password)
    if (result.code === 0) {
      await eventStore.fetchRecommendEvents(1)
    } else {
      ElMessage.error(result.message || '登录失败')
    }
  } finally {
    loading.value = false
  }
}

async function handleLogout() {
  await authStore.logout()
}

function openSidePanel(event?: any) {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]?.id) {
      chrome.sidePanel.open({ tabId: tabs[0].id })
    }
  })
  window.close()
}

function severityType(severity: string | null) {
  const types: Record<string, string> = {
    critical: 'danger',
    high: 'danger',
    medium: 'warning',
    low: 'success'
  }
  return types[severity || ''] || 'info'
}

function severityText(severity: string | null) {
  const texts: Record<string, string> = {
    critical: '严重',
    high: '高危',
    medium: '中危',
    low: '低危'
  }
  return texts[severity || ''] || '未知'
}

function truncate(text: string, length: number) {
  return text.length > length ? text.slice(0, length) + '...' : text
}

function formatTime(dateStr: string | null) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  return `${days}天前`
}
</script>

<style scoped>
.popup-container {
  width: 320px;
  padding: 16px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.loading-section {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #409eff;
}

.login-section h2 {
  text-align: center;
  margin-bottom: 20px;
  font-size: 18px;
  color: #333;
}

.user-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #eee;
}

.nickname {
  font-weight: 500;
  color: #333;
}

.unread-section {
  margin-bottom: 12px;
}

.unread-badge {
  background: #ff4444;
  color: white;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
}

.recent-events {
  margin-bottom: 16px;
}

.recent-events h3 {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.event-item {
  padding: 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.event-item:hover {
  background: #f5f7fa;
}

.event-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.title-text {
  font-size: 13px;
  color: #333;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.event-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #999;
}

.loading, .empty {
  padding: 20px;
  text-align: center;
  color: #999;
}
</style>
