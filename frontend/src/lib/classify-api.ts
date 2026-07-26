import { api } from './api-client'
import type { ClassificationResult, ClassificationHistoryItem } from '@/types/api'

export const classifyApi = {
  classify: (description: string) =>
    api.post<ClassificationResult & { id: number }>('/classify', { description }).then((r) => r.data),

  history: (limit = 20, offset = 0) =>
    api
      .get<{ count: number; limit: number; offset: number; results: ClassificationHistoryItem[] }>('/classifications', {
        params: { limit, offset },
      })
      .then((r) => r.data),
}
