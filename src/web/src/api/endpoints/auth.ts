import { api } from '../client'
import type { User } from '@/models'

export interface SessionResponse {
  user: User
  message: string
}

export const authApi = {
  /**
   * Sync user from Authentik to local database.
   * Call this once after OIDC login completes.
   */
  createSession: () => api.post<SessionResponse>('/auth/session'),

  /**
   * Logout (for future session management).
   */
  deleteSession: () => api.delete<void>('/auth/session'),
}
