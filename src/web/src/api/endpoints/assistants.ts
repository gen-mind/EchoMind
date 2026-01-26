import { api } from '../client'
import type {
  Assistant,
  CreateAssistantRequest,
  UpdateAssistantRequest,
  ListAssistantsResponse,
} from '@/models'

export const assistantsApi = {
  list: (params?: { page?: number; limit?: number; is_visible?: boolean }) =>
    api.get<ListAssistantsResponse>('/assistants', params),

  getById: (assistantId: number) => api.get<Assistant>(`/assistants/${assistantId}`),

  create: (data: CreateAssistantRequest) => api.post<Assistant>('/assistants', data),

  update: (assistantId: number, data: Partial<UpdateAssistantRequest>) =>
    api.put<Assistant>(`/assistants/${assistantId}`, data),

  delete: (assistantId: number) => api.delete<void>(`/assistants/${assistantId}`),
}
