import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Send, StopCircle, Bot, User, Loader2, ThumbsUp, ThumbsDown, FileText } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { chatApi, getChatWebSocket, assistantsApi } from '@/api'
import type { ChatMessage, MessageSource } from '@/models'
import { ChatMode } from '@/models'
import {
  Button,
  Textarea,
  ScrollArea,
  Avatar,
  AvatarFallback,
  Card,
  CardContent,
  Badge,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui'
import { cn } from '@/lib/utils'

interface StreamingMessage {
  content: string
  sources: MessageSource[]
  isStreaming: boolean
  error?: string
}

export function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const ws = getChatWebSocket()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const [query, setQuery] = useState('')
  const [selectedAssistantId, setSelectedAssistantId] = useState<number | null>(null)
  const [mode, setMode] = useState<'chat' | 'search'>('chat')
  const [streamingMessage, setStreamingMessage] = useState<StreamingMessage | null>(null)
  const [, setIsConnected] = useState(false)

  // Fetch assistants for selector
  const { data: assistantsData } = useQuery({
    queryKey: ['assistants'],
    queryFn: () => assistantsApi.list({ is_visible: true }),
  })

  const assistants = assistantsData?.assistants || []
  const defaultAssistant = assistants.find((a) => a.isDefault) || assistants[0]

  // Set default assistant
  useEffect(() => {
    if (defaultAssistant && !selectedAssistantId) {
      setSelectedAssistantId(defaultAssistant.id)
    }
  }, [defaultAssistant, selectedAssistantId])

  // Fetch session data
  const { data: sessionData, isLoading: isLoadingSession } = useQuery({
    queryKey: ['chat-session', sessionId],
    queryFn: () => chatApi.getSession(Number(sessionId)),
    enabled: !!sessionId,
  })

  const messages = sessionData?.messages || []

  // Create session mutation
  const createSessionMutation = useMutation({
    mutationFn: chatApi.createSession,
    onSuccess: (newSession) => {
      navigate(`/chat/${newSession.id}`, { replace: true })
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
    },
  })

  // Feedback mutation
  const feedbackMutation = useMutation({
    mutationFn: chatApi.submitFeedback,
  })

  // WebSocket connection and handlers
  useEffect(() => {
    const connect = async () => {
      try {
        if (!ws.isConnected) {
          await ws.connect()
        }
        setIsConnected(true)
      } catch (error) {
        console.error('Failed to connect WebSocket:', error)
        setIsConnected(false)
      }
    }

    connect()

    // Subscribe to events
    const unsubRetrievalStart = ws.on('retrieval.start', () => {
      setStreamingMessage((prev) => ({
        content: prev?.content || '',
        sources: [],
        isStreaming: true,
      }))
    })

    const unsubRetrievalComplete = ws.on('retrieval.complete', (msg) => {
      const sources = (msg as { sources?: MessageSource[] }).sources || []
      setStreamingMessage((prev) => ({
        content: prev?.content || '',
        sources,
        isStreaming: true,
      }))
    })

    const unsubToken = ws.on('generation.token', (msg) => {
      const token = (msg as { token?: string }).token || ''
      setStreamingMessage((prev) => ({
        content: (prev?.content || '') + token,
        sources: prev?.sources || [],
        isStreaming: true,
      }))
    })

    const unsubComplete = ws.on('generation.complete', () => {
      setStreamingMessage((prev) =>
        prev ? { ...prev, isStreaming: false } : null
      )
      // Refetch session to get updated messages
      if (sessionId) {
        queryClient.invalidateQueries({ queryKey: ['chat-session', sessionId] })
        queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      }
    })

    const unsubError = ws.on('error', (msg) => {
      const error = msg as { message?: string }
      setStreamingMessage((prev) => ({
        content: prev?.content || '',
        sources: prev?.sources || [],
        isStreaming: false,
        error: error.message || 'An error occurred',
      }))
    })

    return () => {
      unsubRetrievalStart()
      unsubRetrievalComplete()
      unsubToken()
      unsubComplete()
      unsubError()
    }
  }, [ws, sessionId, queryClient])

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingMessage])

  const handleSubmit = async () => {
    if (!query.trim() || streamingMessage?.isStreaming) return

    const trimmedQuery = query.trim()
    setQuery('')
    setStreamingMessage({ content: '', sources: [], isStreaming: true })

    try {
      let currentSessionId = sessionId ? Number(sessionId) : null

      // Create session if needed
      if (!currentSessionId) {
        if (!selectedAssistantId) return

        const newSession = await createSessionMutation.mutateAsync({
          assistantId: selectedAssistantId,
          title: trimmedQuery.slice(0, 50),
          mode: mode === 'chat' ? ChatMode.CHAT_MODE_CHAT : ChatMode.CHAT_MODE_SEARCH,
        })
        currentSessionId = newSession.id
      }

      // Send message via WebSocket
      ws.startChat(currentSessionId, trimmedQuery, mode)
    } catch (error) {
      console.error('Failed to send message:', error)
      setStreamingMessage({
        content: '',
        sources: [],
        isStreaming: false,
        error: 'Failed to send message',
      })
    }
  }

  const handleCancel = () => {
    if (sessionId && streamingMessage?.isStreaming) {
      ws.cancelChat(Number(sessionId))
      setStreamingMessage((prev) =>
        prev ? { ...prev, isStreaming: false } : null
      )
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleFeedback = (messageId: number, isPositive: boolean) => {
    feedbackMutation.mutate({ messageId, isPositive })
  }

  // Render new chat view
  if (!sessionId) {
    const selectedAssistant = assistants.find((a) => a.id === selectedAssistantId)

    return (
      <div className="flex flex-col h-full">
        <div className="flex-1 flex flex-col items-center justify-center p-4">
          <div className="text-center max-w-2xl">
            <h1 className="text-3xl font-bold mb-2">Welcome to EchoMind</h1>
            <p className="text-muted-foreground mb-8">
              Ask questions about your documents, get intelligent answers powered by RAG.
            </p>

            {/* Assistant Selector */}
            <div className="flex items-center justify-center gap-4 mb-8">
              <Select
                value={selectedAssistantId?.toString()}
                onValueChange={(value) => setSelectedAssistantId(Number(value))}
              >
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder="Select assistant" />
                </SelectTrigger>
                <SelectContent>
                  {assistants.map((assistant) => (
                    <SelectItem key={assistant.id} value={assistant.id.toString()}>
                      {assistant.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={mode} onValueChange={(v) => setMode(v as 'chat' | 'search')}>
                <SelectTrigger className="w-[120px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="chat">Chat</SelectItem>
                  <SelectItem value="search">Search</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Starter Messages */}
            {selectedAssistant?.starterMessages && selectedAssistant.starterMessages.length > 0 && (
              <div className="grid gap-2 max-w-md mx-auto mb-8">
                {selectedAssistant.starterMessages.map((starter, idx) => (
                  <Button
                    key={idx}
                    variant="outline"
                    className="h-auto py-3 px-4 text-left justify-start"
                    onClick={() => setQuery(starter)}
                  >
                    {starter}
                  </Button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Input Area */}
        <div className="border-t p-4">
          <div className="max-w-3xl mx-auto">
            <div className="relative">
              <Textarea
                ref={textareaRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a question..."
                className="min-h-[60px] max-h-[200px] pr-12 resize-none"
                rows={1}
              />
              <Button
                onClick={handleSubmit}
                disabled={!query.trim() || !selectedAssistantId || streamingMessage?.isStreaming}
                size="icon"
                className="absolute right-2 bottom-2"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Loading state
  if (isLoadingSession) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Chat session view
  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <ScrollArea className="flex-1 p-4">
        <div className="max-w-3xl mx-auto space-y-6">
          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              onFeedback={handleFeedback}
            />
          ))}

          {/* Streaming message */}
          {streamingMessage && (
            <div className="flex gap-3">
              <Avatar className="h-8 w-8">
                <AvatarFallback>
                  <Bot className="h-4 w-4" />
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 space-y-2">
                {streamingMessage.sources.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {streamingMessage.sources.slice(0, 3).map((source, idx) => (
                      <Badge key={idx} variant="secondary" className="text-xs">
                        <FileText className="h-3 w-3 mr-1" />
                        {source.title || `Source ${idx + 1}`}
                      </Badge>
                    ))}
                  </div>
                )}
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  {streamingMessage.content ? (
                    <ReactMarkdown>{streamingMessage.content}</ReactMarkdown>
                  ) : streamingMessage.isStreaming ? (
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Thinking...</span>
                    </div>
                  ) : null}
                </div>
                {streamingMessage.error && (
                  <p className="text-sm text-destructive">{streamingMessage.error}</p>
                )}
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Input Area */}
      <div className="border-t p-4">
        <div className="max-w-3xl mx-auto">
          <div className="relative">
            <Textarea
              ref={textareaRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a follow-up question..."
              className="min-h-[60px] max-h-[200px] pr-12 resize-none"
              rows={1}
            />
            {streamingMessage?.isStreaming ? (
              <Button
                onClick={handleCancel}
                variant="destructive"
                size="icon"
                className="absolute right-2 bottom-2"
              >
                <StopCircle className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                onClick={handleSubmit}
                disabled={!query.trim()}
                size="icon"
                className="absolute right-2 bottom-2"
              >
                <Send className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

interface MessageBubbleProps {
  message: ChatMessage
  onFeedback: (messageId: number, isPositive: boolean) => void
}

function MessageBubble({ message, onFeedback }: MessageBubbleProps) {
  const isUser = message.role === 'MESSAGE_ROLE_USER'

  return (
    <div className={cn('flex gap-3', isUser && 'flex-row-reverse')}>
      <Avatar className="h-8 w-8">
        <AvatarFallback>
          {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
        </AvatarFallback>
      </Avatar>
      <div className={cn('flex-1 space-y-2', isUser && 'text-right')}>
        <Card className={cn('inline-block max-w-full', isUser && 'bg-primary text-primary-foreground')}>
          <CardContent className="p-3">
            <div className={cn('prose prose-sm dark:prose-invert max-w-none', isUser && 'text-inherit')}>
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          </CardContent>
        </Card>

        {/* Feedback buttons for assistant messages */}
        {!isUser && (
          <div className="flex items-center gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => onFeedback(message.id, true)}
                >
                  <ThumbsUp className="h-3 w-3" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Helpful</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => onFeedback(message.id, false)}
                >
                  <ThumbsDown className="h-3 w-3" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Not helpful</TooltipContent>
            </Tooltip>
          </div>
        )}
      </div>
    </div>
  )
}
