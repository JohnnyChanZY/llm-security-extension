// Background Service Worker
import { wsClient } from '../shared/websocket'

// 扩展安装时初始化
chrome.runtime.onInstalled.addListener(() => {
  console.log('LLM安全事件推送插件已安装')

  // 初始化存储
  chrome.storage.local.set({
    unreadCount: 0,
    isLoggedIn: false
  })

  // 更新图标角标
  updateBadge(0)
})

// 监听来自popup/sidepanel的消息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.type) {
    case 'LOGIN':
      handleLogin(message.data)
      break
    case 'LOGOUT':
      handleLogout()
      break
    case 'GET_UNREAD_COUNT':
      sendResponse({ count: getUnreadCount() })
      break
    case 'CONNECT_WS':
      connectWebSocket(message.token)
      break
  }
  return true
})

// 处理登录
async function handleLogin(data: { token: string; user: any }) {
  await chrome.storage.local.set({
    token: { access_token: data.token },
    user: data.user,
    isLoggedIn: true
  })
  connectWebSocket(data.token)
}

// 处理登出
async function handleLogout() {
  await chrome.storage.local.remove(['token', 'user'])
  await chrome.storage.local.set({ isLoggedIn: false, unreadCount: 0 })
  wsClient.disconnect()
  updateBadge(0)
}

// 连接WebSocket
async function connectWebSocket(token: string) {
  const connected = await wsClient.connect(token)

  if (connected) {
    // 监听新事件
    wsClient.on('new_event', (data: any) => {
      handleNewEvent(data.data)
    })

    // 监听未读数量更新
    wsClient.on('unread_count', (data: any) => {
      updateBadge(data.count)
    })
  }
}

// 处理新事件
async function handleNewEvent(event: any) {
  // 更新未读数量
  const result = await chrome.storage.local.get(['unreadCount'])
  const newCount = (result.unreadCount || 0) + 1
  await chrome.storage.local.set({ unreadCount: newCount })
  updateBadge(newCount)

  // 显示通知
  showNotification(event)
}

// 更新图标角标
function updateBadge(count: number) {
  if (count > 0) {
    chrome.action.setBadgeText({ text: count > 99 ? '99+' : String(count) })
    chrome.action.setBadgeBackgroundColor({ color: '#FF4444' })
  } else {
    chrome.action.setBadgeText({ text: '' })
  }
}

// 获取未读数量
async function getUnreadCount(): Promise<number> {
  const result = await chrome.storage.local.get(['unreadCount'])
  return result.unreadCount || 0
}

// 显示通知
function showNotification(event: any) {
  const severityEmoji: Record<string, string> = {
    critical: '🔴',
    high: '🟠',
    medium: '🟡',
    low: '🟢'
  }

  chrome.notifications.create({
    type: 'basic',
    iconUrl: '/src/assets/icon48.png',
    title: `${severityEmoji[event.severity] || '🔔'} 新安全事件`,
    message: event.title,
    priority: event.severity === 'critical' || event.severity === 'high' ? 2 : 1
  })
}

// 监听通知点击
chrome.notifications.onClicked.addListener((notificationId) => {
  // 打开侧边栏
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]?.id) {
      chrome.sidePanel.open({ tabId: tabs[0].id })
    }
  })
})

// 定时检查连接状态
chrome.alarms.create('checkConnection', { periodInMinutes: 1 })

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'checkConnection') {
    checkConnection()
  }
})

async function checkConnection() {
  const result = await chrome.storage.local.get(['isLoggedIn', 'token'])
  if (result.isLoggedIn && result.token?.access_token) {
    if (!wsClient.getConnectionStatus()) {
      connectWebSocket(result.token.access_token)
    }
  }
}

// 初始化时尝试连接
;(async () => {
  const result = await chrome.storage.local.get(['isLoggedIn', 'token'])
  if (result.isLoggedIn && result.token?.access_token) {
    connectWebSocket(result.token.access_token)
  }
})()
