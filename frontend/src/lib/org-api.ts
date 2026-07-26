import { api } from './api-client'
import type { User, UserRole } from '@/types/api'

export interface InviteMemberPayload {
  email: string
  password: string
  full_name: string
  role: UserRole
}

export const orgApi = {
  listMembers: () => api.get<User[]>('/organizations/members').then((r) => r.data),

  inviteMember: (payload: InviteMemberPayload) => api.post<User>('/organizations/members', payload).then((r) => r.data),

  updateRole: (userId: number, role: UserRole) =>
    api.put<User>(`/organizations/members/${userId}/role`, { role }).then((r) => r.data),
}
