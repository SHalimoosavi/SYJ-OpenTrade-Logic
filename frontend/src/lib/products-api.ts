import { api } from './api-client'
import type { Product, ProductListResponse, ImportSummary } from '@/types/api'

export interface ProductCreatePayload {
  sku: string
  name: string
  description?: string
  hts_code?: string
  duty_rate?: string
}

export const productsApi = {
  list: (limit = 50, offset = 0) =>
    api.get<ProductListResponse>('/products', { params: { limit, offset } }).then((r) => r.data),

  create: (payload: ProductCreatePayload) => api.post<Product>('/products', payload).then((r) => r.data),

  update: (id: number, payload: Partial<ProductCreatePayload>) =>
    api.put<Product>(`/products/${id}`, payload).then((r) => r.data),

  remove: (id: number) => api.delete(`/products/${id}`),

  importFile: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api
      .post<ImportSummary>('/products/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data)
  },
}
