import { api } from '../client'
import type { User, UpdateUserRequest, ListUsersResponse } from '@/models'

export const usersApi = {
  getMe: () => api.get<User>('/users/me'),

  updateMe: (data: UpdateUserRequest) => api.put<User>('/users/me', data),

  list: (params?: { page?: number; limit?: number; is_active?: boolean }) =>
    api.get<ListUsersResponse>('/users', params),

  getById: (userId: number) => api.get<User>(`/users/${userId}`),
}
