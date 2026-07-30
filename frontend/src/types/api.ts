// Mirrors server_fastapi/schemas.py exactly -- keep these in sync if the
// backend schemas change.

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface User {
  id: number
  email: string
  full_name: string
  role: 'viewer' | 'member' | 'admin' | 'owner'
  is_active: boolean
  organization_id: number
}

export interface Organization {
  id: number
  name: string
  slug: string
}

export interface DecisionStep {
  node_code: string
  node_description: string
  rule_applied: string
  reasoning: string
  score: number
}

export interface AlternativeCode {
  code: string
  description: string
  confidence: number
  reason_not_selected: string
}

export interface RelatedRuling {
  id: string
  url: string
  date: string
  title: string
  hts_codes: string[]
  gri_rules_cited: string[]
  excerpt: string
  score: number
  matched_terms: string[]
}

export interface ClassificationResult {
  id?: number
  product_description: string
  final_code: string | null
  final_description: string | null
  confidence: number
  is_classified: boolean
  duty_rate: string | null
  unresolved_reason: string | null
  decision_path: DecisionStep[]
  alternatives: AlternativeCode[]
  supporting_notes: string[]
  related_rulings: RelatedRuling[]
}

export interface ClassificationHistoryItem {
  id: number
  product_description: string
  final_code: string | null
  final_description: string | null
  confidence: number | null
  is_classified: boolean
  duty_rate: string | null
  unresolved_reason: string | null
  created_at: string
}

export interface Product {
  id: number
  sku: string
  name: string
  description: string | null
  hts_code: string | null
  duty_rate: string | null
  created_at: string
  updated_at: string
}

export interface ProductListResponse {
  count: number
  limit: number
  offset: number
  results: Product[]
}

export interface ImportRowResult {
  row_number: number
  sku: string | null
  status: 'created' | 'updated' | 'error'
  error?: string | null
}

export interface ImportSummary {
  total_rows: number
  created: number
  updated: number
  errors: number
  row_results: ImportRowResult[]
}

export interface ProgramDuty {
  program: string
  chapter99_code: string
  legal_basis: string
  rate: number
  amount: number
  notes: string
  source_url: string
}

export interface ADCVDFlag {
  case_numbers: string[]
  product_scope: string
  countries: string[]
  notes: string
}

export interface DutyCalculationResult {
  hts_code: string
  country_of_origin: string
  declared_value: number
  base_duty_rate: number | null
  base_duty_amount: number | null
  base_rate_raw: string | null
  program_duties: ProgramDuty[]
  adcvd_flags: ADCVDFlag[]
  total_duty_rate: number | null
  total_duty_amount: number | null
  warnings: string[]
  as_of_date: string
  disclaimer: string
}

export interface AuditLogEntry {
  id: number
  user_email: string | null
  action: string
  resource_type: string
  resource_id: string | null
  details: Record<string, unknown> | null
  created_at: string
}

export interface AuditLogListResponse {
  count: number
  limit: number
  offset: number
  results: AuditLogEntry[]
}

export interface Webhook {
  id: number
  url: string
  event_types: string[]
  is_active: boolean
  created_at: string
  secret?: string | null
}

export interface WebhookDelivery {
  id: number
  webhook_id: number
  event_type: string
  response_status: number | null
  error: string | null
  created_at: string
}

export type UserRole = 'viewer' | 'member' | 'admin' | 'owner'

export const ROLE_RANK: Record<UserRole, number> = {
  viewer: 0,
  member: 1,
  admin: 2,
  owner: 3,
}

export function roleAtLeast(userRole: UserRole, required: UserRole): boolean {
  return ROLE_RANK[userRole] >= ROLE_RANK[required]
}
