<template>
  <div class="sidepanel-container">
    <!-- 加载中 -->
    <div v-if="initializing" class="loading-page">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <!-- 未登录 -->
    <div v-else-if="!authStore.isLoggedIn" class="login-page">
      <h1>LLM安全事件推送</h1>
      <p class="desc">及时了解LLM安全领域的最新动态</p>

      <el-tabs v-model="loginTab">
        <el-tab-pane label="登录" name="login">
          <el-form :model="loginForm" @submit.prevent="handleLogin">
            <el-form-item>
              <el-input
                v-model="loginForm.email"
                placeholder="邮箱"
                prefix-icon="User"
                size="large"
              />
            </el-form-item>
            <el-form-item>
              <el-input
                v-model="loginForm.password"
                type="password"
                placeholder="密码"
                prefix-icon="Lock"
                size="large"
                show-password
              />
            </el-form-item>
            <el-button
              type="primary"
              native-type="submit"
              :loading="loading"
              size="large"
              block
            >
              登录
            </el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="注册" name="register">
          <el-form :model="registerForm" @submit.prevent="handleRegister">
            <el-form-item>
              <el-input
                v-model="registerForm.email"
                placeholder="邮箱"
                prefix-icon="User"
                size="large"
              />
            </el-form-item>
            <el-form-item>
              <el-input
                v-model="registerForm.nickname"
                placeholder="昵称（可选）"
                prefix-icon="UserFilled"
                size="large"
              />
            </el-form-item>
            <el-form-item>
              <el-input
                v-model="registerForm.password"
                type="password"
                placeholder="密码（至少6位）"
                prefix-icon="Lock"
                size="large"
                show-password
              />
            </el-form-item>
            <el-form-item>
              <el-input
                v-model="registerForm.confirmPassword"
                type="password"
                placeholder="确认密码"
                prefix-icon="Lock"
                size="large"
                show-password
              />
            </el-form-item>
            <el-button
              type="primary"
              native-type="submit"
              :loading="loading"
              size="large"
              block
            >
              注册
            </el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 已登录 -->
    <div v-else class="main-page">
      <!-- 顶部导航 -->
      <header class="header">
        <span class="title">LLM安全事件</span>
        <div class="header-right">
          <el-badge :value="eventStore.unreadCount" :hidden="eventStore.unreadCount === 0">
            <el-button :icon="Bell" circle />
          </el-badge>
          <el-dropdown @command="handleUserCommand">
            <el-avatar :size="32" class="avatar">
              {{ authStore.user?.nickname?.[0] || authStore.user?.email?.[0] }}
            </el-avatar>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="settings">
                  <el-icon><Setting /></el-icon>
                  设置
                </el-dropdown-item>
                <el-dropdown-item command="logout" divided>
                  <el-icon><SwitchButton /></el-icon>
                  登出
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- 主内容 -->
      <main class="main-content">
        <router-view />
      </main>

      <!-- 底部导航 -->
      <nav class="bottom-nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          :class="{ active: $route.path === item.path }"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.text }}</span>
        </router-link>
      </nav>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Bell, Setting, SwitchButton, HomeFilled, Search, User, Loading } from '@element-plus/icons-vue'
import { useAuthStore, useEventStore } from '../shared/stores'
import router from './router'

const authStore = useAuthStore()
const eventStore = useEventStore()

const initializing = ref(true)
const loginTab = ref('login')
const loading = ref(false)

const loginForm = ref({
  email: '',
  password: ''
})

const registerForm = ref({
  email: '',
  nickname: '',
  password: '',
  confirmPassword: ''
})

const navItems = [
  { path: '/', icon: HomeFilled, text: '首页' },
  { path: '/search', icon: Search, text: '搜索' },
  { path: '/settings', icon: User, text: '设置' }
]

onMounted(async () => {
  await authStore.init()
  initializing.value = false
  if (authStore.isLoggedIn) {
    await eventStore.fetchUnreadCount()
  }
})

async function handleLogin() {
  loading.value = true
  try {
    const result = await authStore.login(loginForm.value.email, loginForm.value.password)
    if (result.code === 0) {
      ElMessage.success('登录成功')
    } else {
      ElMessage.error(result.message || '登录失败')
    }
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  if (registerForm.value.password !== registerForm.value.confirmPassword) {
    ElMessage.error('两次输入的密码不一致')
    return
  }

  if (registerForm.value.password.length < 6) {
    ElMessage.error('密码至少6位')
    return
  }

  loading.value = true
  try {
    const result = await authStore.register(
      registerForm.value.email,
      registerForm.value.password,
      registerForm.value.nickname
    )
    if (result.code === 0) {
      ElMessage.success('注册成功，请登录')
      loginTab.value = 'login'
      loginForm.value.email = registerForm.value.email
    } else {
      ElMessage.error(result.message || '注册失败')
    }
  } finally {
    loading.value = false
  }
}

function handleUserCommand(command: string) {
  if (command === 'settings') {
    router.push('/settings')
  } else if (command === 'logout') {
    authStore.logout()
    ElMessage.success('已登出')
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f5f7fa;
}
</style>

<style scoped>
.sidepanel-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

/* 登录页 */
.login-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 24px;
  background: white;
}

/* 加载页 */
.loading-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #999;
}

.loading-page p {
  font-size: 14px;
}

.login-page h1 {
  text-align: center;
  margin-bottom: 8px;
  font-size: 24px;
  color: #333;
}

.login-page .desc {
  text-align: center;
  color: #999;
  margin-bottom: 32px;
}

/* 主页面 */
.main-page {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: white;
  border-bottom: 1px solid #eee;
}

.header .title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.avatar {
  cursor: pointer;
  background: #409eff;
}

.main-content {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 60px;
}

/* 底部导航 */
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  justify-content: space-around;
  background: white;
  border-top: 1px solid #eee;
  padding: 8px 0;
  z-index: 100;
}

.bottom-nav a {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: #999;
  text-decoration: none;
  font-size: 12px;
  padding: 4px 16px;
}

.bottom-nav a.active {
  color: #409eff;
}

.bottom-nav a .el-icon {
  font-size: 20px;
}
</style>
