import { api } from '../client'
import type {
  EmbeddingModel,
  CreateEmbeddingModelRequest,
  ListEmbeddingModelsResponse,
  GetActiveEmbeddingModelResponse,
  ActivateEmbeddingModelResponse,
} from '@/models'

export const embeddingModelsApi = {
  list: () => api.get<ListEmbeddingModelsResponse>('/embedding-models'),

  getById: (modelId: number) => api.get<EmbeddingModel>(`/embedding-models/${modelId}`),

  create: (data: CreateEmbeddingModelRequest) =>
    api.post<EmbeddingModel>('/embedding-models', data),

  delete: (modelId: number) => api.delete<void>(`/embedding-models/${modelId}`),

  getActive: () => api.get<GetActiveEmbeddingModelResponse>('/embedding-models/active'),

  activate: (modelId: number) =>
    api.put<ActivateEmbeddingModelResponse>(`/embedding-models/${modelId}/activate`),
}
