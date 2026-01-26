import { api } from '../client'
import type {
  LLM,
  CreateLLMRequest,
  UpdateLLMRequest,
  ListLLMsResponse,
  TestLLMResponse,
} from '@/models'

export const llmsApi = {
  list: (params?: { page?: number; limit?: number; is_active?: boolean }) =>
    api.get<ListLLMsResponse>('/llms', params),

  getById: (llmId: number) => api.get<LLM>(`/llms/${llmId}`),

  create: (data: CreateLLMRequest) => api.post<LLM>('/llms', data),

  update: (llmId: number, data: Partial<UpdateLLMRequest>) =>
    api.put<LLM>(`/llms/${llmId}`, data),

  delete: (llmId: number) => api.delete<void>(`/llms/${llmId}`),

  test: (llmId: number) => api.post<TestLLMResponse>(`/llms/${llmId}/test`),
}
