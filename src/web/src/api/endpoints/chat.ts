import { api } from '../client'
import type {
  ChatSession,
  ChatMessage,
  CreateChatSessionRequest,
  ListChatSessionsResponse,
  GetChatSessionResponse,
  ListMessagesResponse,
  GetMessageSourcesResponse,
  SubmitFeedbackRequest,
  SubmitFeedbackResponse,
} from '@/models'

export const chatApi = {
  // Sessions
  listSessions: (params?: { page?: number; limit?: number; assistant_id?: number }) =>
    api.get<ListChatSessionsResponse>('/chat/sessions', params),

  getSession: (sessionId: number) =>
    api.get<GetChatSessionResponse>(`/chat/sessions/${sessionId}`),

  createSession: (data: CreateChatSessionRequest) =>
    api.post<ChatSession>('/chat/sessions', data),

  updateSession: (sessionId: number, data: { title?: string }) =>
    api.put<ChatSession>(`/chat/sessions/${sessionId}`, data),

  deleteSession: (sessionId: number) => api.delete<void>(`/chat/sessions/${sessionId}`),

  // Messages
  listMessages: (sessionId: number, params?: { page?: number; limit?: number }) =>
    api.get<ListMessagesResponse>(`/chat/sessions/${sessionId}/messages`, params),

  getMessage: (messageId: number) => api.get<ChatMessage>(`/chat/messages/${messageId}`),

  getMessageSources: (messageId: number) =>
    api.get<GetMessageSourcesResponse>(`/chat/messages/${messageId}/sources`),

  // Feedback
  submitFeedback: (data: SubmitFeedbackRequest) =>
    api.post<SubmitFeedbackResponse>('/chat/feedback', data),
}
