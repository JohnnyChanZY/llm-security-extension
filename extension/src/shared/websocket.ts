// WebSocket客户端
import type { Event } from './types'

type MessageHandler = (data: any) => void

class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 3000
  private handlers: Map<string, MessageHandler[]> = new Map()
  private isConnected = false
  private isReconnecting = false  // 防止并发重连
  private currentToken: string | null = null

  constructor(baseUrl: string = 'ws://localhost:8000') {
    this.url = `${baseUrl}/ws/events`
  }

  async connect(token: string): Promise<boolean> {
    // 如果已连接，先断开
    if (this.ws && this.isConnected) {
      this.disconnect()
    }

    this.currentToken = token

    return new Promise((resolve) => {
      try {
        this.ws = new WebSocket(`${this.url}?token=${token}`)

        this.ws.onopen = () => {
          console.log('WebSocket连接成功')
          this.isConnected = true
          this.isReconnecting = false
          this.reconnectAttempts = 0
          this.startHeartbeat()
          resolve(true)
        }

        this.ws.onmessage = (event) => {
          // 修复：trim() 处理服务端可能携带的换行符等多余字符
          const raw = typeof event.data === 'string' ? event.data.trim() : event.data
          if (raw === 'pong') {
            return
          }
          try {
            const data = JSON.parse(raw)
            this.handleMessage(data)
          } catch (e) {
            console.error('解析消息失败:', e)
          }
        }

        this.ws.onclose = (event) => {
          console.log('WebSocket连接关闭:', event.code, event.reason)
          this.isConnected = false
          this.stopHeartbeat()

          // 4001=认证失败, 4002=用户不存在，不重连
          if (event.code === 4001 || event.code === 4002) {
            console.log('认证失败，不再重连')
            resolve(false)
            return
          }

          // 正常关闭(1000)也不重连
          if (event.code === 1000) {
            resolve(true)
            return
          }

          resolve(false)
          this.scheduleReconnect()
        }

        this.ws.onerror = (error) => {
          console.error('WebSocket错误:', error)
          this.isConnected = false
          // onerror 后会触发 onclose，由 onclose 处理重连
        }
      } catch (error) {
        console.error('WebSocket连接失败:', error)
        resolve(false)
      }
    })
  }

  private heartbeatTimer: ReturnType<typeof setInterval> | null = null

  private startHeartbeat() {
    this.stopHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.isConnected && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send('ping')
      }
    }, 30000)
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private scheduleReconnect() {
    // 防止并发重连
    if (this.isReconnecting) return
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('已达到最大重连次数，停止重连')
      return
    }

    this.isReconnecting = true
    this.reconnectAttempts++

    // 指数退避：避免频繁重连造成闪烁
    const delay = this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1)
    console.log(`${delay}ms 后尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`)

    setTimeout(async () => {
      // 优先使用记录的 token，其次从 storage 读取
      let token = this.currentToken
      if (!token) {
        const result = await chrome.storage.local.get(['token'])
        token = result.token?.access_token ?? null
      }

      if (token) {
        this.isReconnecting = false
        this.connect(token)
      } else {
        console.log('无可用 token，停止重连')
        this.isReconnecting = false
      }
    }, delay)
  }

  disconnect() {
    this.stopHeartbeat()
    this.reconnectAttempts = this.maxReconnectAttempts  // 阻止 onclose 触发重连
    this.currentToken = null
    if (this.ws) {
      this.ws.close(1000, 'Normal closure')
      this.ws = null
    }
    this.isConnected = false
    this.isReconnecting = false
  }

  on(event: string, handler: MessageHandler) {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, [])
    }
    this.handlers.get(event)!.push(handler)
  }

  off(event: string, handler: MessageHandler) {
    const handlers = this.handlers.get(event)
    if (handlers) {
      const index = handlers.indexOf(handler)
      if (index > -1) {
        handlers.splice(index, 1)
      }
    }
  }

  private handleMessage(data: any) {
    const type = data.type
    if (type && this.handlers.has(type)) {
      this.handlers.get(type)!.forEach((handler) => handler(data))
    }
  }

  getConnectionStatus(): boolean {
    return this.isConnected
  }
}

export const wsClient = new WebSocketClient()