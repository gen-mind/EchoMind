import { api } from '../client'
import type {
  Connector,
  CreateConnectorRequest,
  UpdateConnectorRequest,
  ListConnectorsResponse,
  TriggerSyncResponse,
  GetConnectorStatusResponse,
  ConnectorType,
  ConnectorStatus,
} from '@/models'

export const connectorsApi = {
  list: (params?: {
    page?: number
    limit?: number
    type?: ConnectorType
    status?: ConnectorStatus
  }) => api.get<ListConnectorsResponse>('/connectors', params),

  getById: (connectorId: number) => api.get<Connector>(`/connectors/${connectorId}`),

  create: (data: CreateConnectorRequest) => api.post<Connector>('/connectors', data),

  update: (connectorId: number, data: Partial<UpdateConnectorRequest>) =>
    api.put<Connector>(`/connectors/${connectorId}`, data),

  delete: (connectorId: number) => api.delete<void>(`/connectors/${connectorId}`),

  triggerSync: (connectorId: number) =>
    api.post<TriggerSyncResponse>(`/connectors/${connectorId}/sync`),

  getStatus: (connectorId: number) =>
    api.get<GetConnectorStatusResponse>(`/connectors/${connectorId}/status`),
}
