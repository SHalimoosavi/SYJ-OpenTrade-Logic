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
