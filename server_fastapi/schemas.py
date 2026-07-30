"""
SYJ OpenTrade Logic - Pydantic schemas
Request/response contracts for the FastAPI layer. FastAPI uses these to
auto-generate the OpenAPI/Swagger docs at /docs -- no hand-written spec
needed anymore (server/openapi_spec.py from v0.2.0 is now obsolete).
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ClassifyRequest(BaseModel):
    description: str = Field(..., min_length=1, description="Product description to classify")


class DecisionStepOut(BaseModel):
    node_code: str
    node_description: str
    rule_applied: str
    reasoning: str
    score: float


class AlternativeCodeOut(BaseModel):
    code: str
    description: str
    confidence: float
    reason_not_selected: str


class RulingOut(BaseModel):
    """A CROSS ruling surfaced as supporting precedent -- AI/search assists
    by surfacing this, it never overrides the deterministic GRI engine's
    own decision."""
    id: str
    url: str
    date: str
    title: str
    hts_codes: List[str]
    gri_rules_cited: List[str]
    excerpt: str
    score: float
    matched_terms: List[str]


class ClassificationOut(BaseModel):
    id: int
    product_description: str
    final_code: Optional[str]
    final_description: Optional[str]
    confidence: float
    is_classified: bool
    duty_rate: Optional[str]
    unresolved_reason: Optional[str]
    decision_path: List[DecisionStepOut]
    alternatives: List[AlternativeCodeOut]
    supporting_notes: List[str]
    related_rulings: List[RulingOut] = []


class ClassificationHistoryItem(BaseModel):
    id: int
    product_description: str
    final_code: Optional[str]
    final_description: Optional[str]
    confidence: Optional[float]
    is_classified: bool
    duty_rate: Optional[str]
    unresolved_reason: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ClassificationListOut(BaseModel):
    count: int
    limit: int
    offset: int
    results: List[ClassificationHistoryItem]


class DeleteOut(BaseModel):
    deleted: bool
    id: int


class HealthOut(BaseModel):
    status: str
    service: str
    version: str


# ---------------------------------------------------------------------------
# v0.4.0 - Auth, Organizations, Users, Product Catalog
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    """Registers a brand-new organization plus its first user (the owner)."""
    organization_name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    organization_id: int

    class Config:
        from_attributes = True


class OrganizationOut(BaseModel):
    id: int
    name: str
    slug: str

    class Config:
        from_attributes = True


class InviteUserRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=200)
    role: str = Field(default="member")


class UpdateUserRoleRequest(BaseModel):
    role: str


class ProductCreateRequest(BaseModel):
    sku: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    hts_code: Optional[str] = None
    duty_rate: Optional[str] = None


class ProductUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    hts_code: Optional[str] = None
    duty_rate: Optional[str] = None


class ProductOut(BaseModel):
    id: int
    sku: str
    name: str
    description: Optional[str]
    hts_code: Optional[str]
    duty_rate: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductListOut(BaseModel):
    count: int
    limit: int
    offset: int
    results: List[ProductOut]


class ImportRowResult(BaseModel):
    row_number: int
    sku: Optional[str]
    status: str  # "created" | "updated" | "error"
    error: Optional[str] = None


class ImportSummaryOut(BaseModel):
    total_rows: int
    created: int
    updated: int
    errors: int
    row_results: List[ImportRowResult]


# ---------------------------------------------------------------------------
# v0.6.0 - CROSS Rulings Search (BM25, zero-dependency lexical search)
# ---------------------------------------------------------------------------

class RulingsSearchResponse(BaseModel):
    query: str
    count: int
    results: List[RulingOut]


# ---------------------------------------------------------------------------
# v0.7.0 - Duty Calculator (Section 301/232/IEEPA + AD/CVD flagging)
# ---------------------------------------------------------------------------

class DutyCalculateRequest(BaseModel):
    hts_code: str = Field(..., min_length=1, description="Full HTS code, e.g. 8467.21.00.10")
    country_of_origin: str = Field(..., min_length=2, max_length=2, description="2-letter ISO country code, e.g. CN")
    declared_value: float = Field(..., gt=0, description="Declared customs value in USD")
    general_duty_rate: Optional[str] = Field(
        None, description="Base HTS duty rate string, e.g. '1.7%' or 'Free'. If omitted and hts_code matches a known code, may be looked up automatically."
    )


class ProgramDutyOut(BaseModel):
    program: str
    chapter99_code: str
    legal_basis: str
    rate: float
    amount: float
    notes: str
    source_url: str


class ADCVDFlagOut(BaseModel):
    case_numbers: List[str]
    product_scope: str
    countries: List[str]
    notes: str


class DutyCalculationOut(BaseModel):
    hts_code: str
    country_of_origin: str
    declared_value: float
    base_duty_rate: Optional[float]
    base_duty_amount: Optional[float]
    base_rate_raw: Optional[str]
    program_duties: List[ProgramDutyOut]
    adcvd_flags: List[ADCVDFlagOut]
    total_duty_rate: Optional[float]
    total_duty_amount: Optional[float]
    warnings: List[str]
    as_of_date: str
    disclaimer: str


# ---------------------------------------------------------------------------
# v0.8.0 - Audit Trails, Webhooks, Reports
# ---------------------------------------------------------------------------

class AuditLogOut(BaseModel):
    id: int
    user_email: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListOut(BaseModel):
    count: int
    limit: int
    offset: int
    results: List[AuditLogOut]


class WebhookCreateRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=500)
    event_types: List[str] = Field(..., min_length=1)


class WebhookOut(BaseModel):
    id: int
    url: str
    event_types: List[str]
    is_active: bool
    created_at: datetime
    secret: Optional[str] = None  # only returned once, at creation time


class WebhookListOut(BaseModel):
    results: List[WebhookOut]


class WebhookDeliveryOut(BaseModel):
    id: int
    webhook_id: int
    event_type: str
    response_status: Optional[int]
    error: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class WebhookTestRequest(BaseModel):
    event_type: str = "webhook.test"
