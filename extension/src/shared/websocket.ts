// WebSocket客户端
import type { Event } from './types'

type MessageHandler = (data: any) => void
type EventHandler = (event: Event) => void

class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 3000
  private handlers: Map<string, MessageHandler[]> = new Map()
  private isConnected = false

  constructor(baseUrl: string = 'ws://localhost:8000') {
    this.url = `${baseUrl}/ws/events`
  }

  async connect(token: string): Promise<boolean> {
    return new Promise((resolve) => {
      try {
        this.ws = new WebSocket(`${this.url}?token=${token}`)

        this.ws.onopen = () => {
          console.log('WebSocket连接成功')
          this.isConnected = true
          this.reconnectAttempts = 0
          resolve(true)

          // 开始心跳
          this.startHeartbeat()
        }

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            this.handleMessage(data)
          } catch (e) {
            console.error('解析消息失败:', e)
          }
        }

        this.ws.onclose = () => {
          console.log('WebSocket连接关闭')
          this.isConnected = false
          this.stopHeartbeat()
          this.attemptReconnect()
        }

        this.ws.onerror = (error) => {
          console.error('WebSocket错误:', error)
          this.isConnected = false
          resolve(false)
        }
      } catch (error) {
        console.error('WebSocket连接失败:', error)
        resolve(false)
      }
    })
  }

  private heartbeatTimer: number | null = null

  private startHeartbeat() {
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.isConnected) {
        this.ws.send('ping')
      }
    }, 30000) as unknown as number
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private async attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('达到最大重连次数')
      return
    }

    this.reconnectAttempts++
    console.log(`尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`)

    await new Promise((resolve) => setTimeout(resolve, this.reconnectDelay))

    // 获取token并重连
    const result = await chrome.storage.local.get(['token'])
    if (result.token?.access_token) {
      this.connect(result.token.access_token)
    }
  }

  disconnect() {
    this.stopHeartbeat()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.isConnected = false
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
