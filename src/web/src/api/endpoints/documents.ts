import { api } from '../client'
import type {
  Document,
  ListDocumentsResponse,
  SearchDocumentsResponse,
  DocumentStatus,
} from '@/models'

export const documentsApi = {
  list: (params?: {
    page?: number
    limit?: number
    connector_id?: number
    status?: DocumentStatus
  }) => api.get<ListDocumentsResponse>('/documents', params),

  getById: (documentId: number) => api.get<Document>(`/documents/${documentId}`),

  delete: (documentId: number) => api.delete<void>(`/documents/${documentId}`),

  search: (params: { query: string; connector_id?: number; limit?: number; min_score?: number }) =>
    api.get<SearchDocumentsResponse>('/documents/search', params),
}
