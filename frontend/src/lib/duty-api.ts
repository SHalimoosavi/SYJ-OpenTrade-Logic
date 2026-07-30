import { api } from './api-client'
import type { DutyCalculationResult } from '@/types/api'

export interface DutyCalculateRequest {
  hts_code: string
  country_of_origin: string
  declared_value: number
  general_duty_rate?: string
}

export const dutyApi = {
  calculate: (payload: DutyCalculateRequest) =>
    api.post<DutyCalculationResult>('/duty/calculate', payload).then((r) => r.data),
}
