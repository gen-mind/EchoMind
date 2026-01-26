import { getUser } from '@/auth/oidc'

export type MessageType =
  | 'chat.start'
  | 'chat.cancel'
  | 'ping'
  | 'retrieval.start'
  | 'retrieval.complete'
  | 'generation.token'
  | 'generation.complete'
  | 'error'
  | 'pong'

export interface WsMessage {
  type: MessageType
  [key: string]: unknown
}

export interface ChatStartMessage {
  type: 'chat.start'
  session_id: number
  query: string
  mode?: 'chat' | 'search'
}

export interface RetrievalStartMessage {
  type: 'retrieval.start'
  session_id: number
  query: string
  rephrased_query: string
}

export interface RetrievalCompleteMessage {
  type: 'retrieval.complete'
  session_id: number
  sources: Array<{
    document_id: number
    chunk_id: string
    score: number
    title?: string
    snippet?: string
  }>
}

export interface GenerationTokenMessage {
  type: 'generation.token'
  session_id: number
  token: string
}

export interface GenerationCompleteMessage {
  type: 'generation.complete'
  session_id: number
  message_id: number
  token_count: number
}

export interface ErrorMessage {
  type: 'error'
  code: string
  message: string
}

type WsEventHandler = (message: WsMessage) => void

export class ChatWebSocket {
  private ws: WebSocket | null = null
  private handlers: Map<MessageType, Set<WsEventHandler>> = new Map()
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000

  async connect(): Promise<void> {
    const user = await getUser()
    if (!user?.access_token) {
      throw new Error('Not authenticated')
    }

    const wsUrl = import.meta.env.VITE_WS_URL || `ws://${window.location.host}/api/v1/ws/chat`
    const url = `${wsUrl}?token=${user.access_token}`

    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(url)

      this.ws.onopen = () => {
        this.reconnectAttempts = 0
        resolve()
      }

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        reject(error)
      }

      this.ws.onclose = (event) => {
        if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++
          setTimeout(() => this.connect(), this.reconnectDelay * this.reconnectAttempts)
        }
      }

      this.ws.onmessage = (event) => {
        try {
          const message: WsMessage = JSON.parse(event.data)
          this.dispatch(message)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }
    })
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close(1000)
      this.ws = null
    }
  }

  send(message: WsMessage): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected')
    }
    this.ws.send(JSON.stringify(message))
  }

  startChat(sessionId: number, query: string, mode: 'chat' | 'search' = 'chat'): void {
    this.send({
      type: 'chat.start',
      session_id: sessionId,
      query,
      mode,
    })
  }

  cancelChat(sessionId: number): void {
    this.send({
      type: 'chat.cancel',
      session_id: sessionId,
    })
  }

  ping(): void {
    this.send({ type: 'ping' })
  }

  on(type: MessageType, handler: WsEventHandler): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set())
    }
    this.handlers.get(type)!.add(handler)

    // Return unsubscribe function
    return () => {
      this.handlers.get(type)?.delete(handler)
    }
  }

  private dispatch(message: WsMessage): void {
    const handlers = this.handlers.get(message.type)
    if (handlers) {
      handlers.forEach((handler) => handler(message))
    }
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

// Singleton instance
let chatWs: ChatWebSocket | null = null

export function getChatWebSocket(): ChatWebSocket {
  if (!chatWs) {
    chatWs = new ChatWebSocket()
  }
  return chatWs
}
