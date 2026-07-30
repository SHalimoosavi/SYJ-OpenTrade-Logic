import { api } from './api-client'
import type { Webhook, WebhookDelivery } from '@/types/api'

export interface WebhookCreatePayload {
  url: string
  event_types: string[]
}

export const webhooksApi = {
  list: () => api.get<{ results: Webhook[] }>('/webhooks').then((r) => r.data.results),

  create: (payload: WebhookCreatePayload) => api.post<Webhook>('/webhooks', payload).then((r) => r.data),

  remove: (id: number) => api.delete(`/webhooks/${id}`),

  test: (id: number) =>
    api.post<{ success: boolean; status_code: number | null; error: string | null }>(`/webhooks/${id}/test`, {
      event_type: 'webhook.test',
    }).then((r) => r.data),

  deliveries: (id: number) => api.get<WebhookDelivery[]>(`/webhooks/${id}/deliveries`).then((r) => r.data),
}
