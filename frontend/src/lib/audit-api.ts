import { api } from './api-client'
import type { AuditLogListResponse } from '@/types/api'

export const auditApi = {
  list: (limit = 50, offset = 0) =>
    api.get<AuditLogListResponse>('/audit-log', { params: { limit, offset } }).then((r) => r.data),
}
