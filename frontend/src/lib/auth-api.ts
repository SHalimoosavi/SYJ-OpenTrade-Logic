import { api } from './api-client'
import type { TokenPair, User } from '@/types/api'

export interface RegisterPayload {
  organization_name: string
  email: string
  password: string
  full_name: string
}

export interface LoginPayload {
  email: string
  password: string
}

export const authApi = {
  register: (payload: RegisterPayload) => api.post<TokenPair>('/auth/register', payload).then((r) => r.data),

  login: (payload: LoginPayload) => api.post<TokenPair>('/auth/login', payload).then((r) => r.data),

  me: () => api.get<User>('/auth/me').then((r) => r.data),
}
