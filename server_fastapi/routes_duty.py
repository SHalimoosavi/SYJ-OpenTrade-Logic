"""
SYJ OpenTrade Logic - Duty calculator routes (v0.7.0)
========================================================
POST /duty/calculate - estimate total duty for an HTS code + country of
origin + declared value. Unauthenticated, like /classify -- this is a
calculation utility, not organization-scoped data.
"""

import os
import sys

from fastapi import APIRouter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.duty_calculator import DutyCalculator  # noqa: E402
from server_fastapi.schemas import DutyCalculateRequest, DutyCalculationOut  # noqa: E402

router = APIRouter(prefix="/duty", tags=["duty"])

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_TRADE_PROGRAMS_PATH = os.environ.get(
    "SYJ_TRADE_PROGRAMS_PATH", os.path.join(_DATA_DIR, "trade_programs_sample.json")
)
_ADCVD_PATH = os.environ.get("SYJ_ADCVD_PATH", os.path.join(_DATA_DIR, "adcvd_sample.json"))

calculator = DutyCalculator(_TRADE_PROGRAMS_PATH, _ADCVD_PATH)


@router.post("/calculate", response_model=DutyCalculationOut)
def calculate_duty(req: DutyCalculateRequest):
    result = calculator.calculate(
        hts_code=req.hts_code,
        country_of_origin=req.country_of_origin,
        declared_value=req.declared_value,
        general_duty_rate=req.general_duty_rate,
    )
    return result.to_dict()
