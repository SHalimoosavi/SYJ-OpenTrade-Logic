"""
SYJ OpenTrade Logic - Duty Calculator (v0.7.0)
=================================================
Computes an ESTIMATED total duty for a classified product, layering:
  1. Base/general HTS duty rate (Column 1 General / MFN rate)
  2. Applicable Section 301/232/IEEPA "Chapter 99" additional duties
  3. AD/CVD scope flags (awareness only -- never a computed rate, since
     actual cash deposit rates are manufacturer/exporter-specific)

CRITICAL HONESTY NOTE: trade remedy duties change with real financial and
legal consequences, sometimes with only days of notice (an executive order
in Feb 2026 ended certain IEEPA tariff actions with no advance public
comment period). This calculator is an ESTIMATION tool built from a small,
dated, manually-curated sample -- see data/trade_programs_sample.json and
data/adcvd_sample.json for their `as_of_date` and `disclaimer` fields,
which are surfaced in every result returned by this module. This is not
legal, customs, or financial advice, and does not replace a licensed
customs broker or the official CBP/USTR sources.
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional


def parse_ad_valorem_rate(rate_str: Optional[str]) -> Optional[float]:
    """
    Converts a simple ad valorem rate string ('16.5%', 'Free') to a
    decimal float (0.165, 0.0). Returns None for anything that ISN'T a
    simple ad valorem rate -- e.g. specific rates ('$0.28/kg') or compound
    rates ('5.3 cents/kg + 5%'), which are real and common in the HTS but
    cannot be safely auto-calculated without unit/weight data this
    calculator doesn't have. Silently guessing wrong on those would be
    worse than clearly saying "cannot auto-calculate."
    """
    if not rate_str:
        return None
    s = rate_str.strip()
    if s.lower() == "free":
        return 0.0
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*%", s)
    if m:
        return float(m.group(1)) / 100
    return None


@dataclass
class ProgramDuty:
    program: str
    chapter99_code: str
    legal_basis: str
    rate: float
    amount: float
    notes: str
    source_url: str


@dataclass
class ADCVDFlag:
    case_numbers: List[str]
    product_scope: str
    countries: List[str]
    notes: str


@dataclass
class DutyCalculationResult:
    hts_code: str
    country_of_origin: str
    declared_value: float
    base_duty_rate: Optional[float]
    base_duty_amount: Optional[float]
    base_rate_raw: Optional[str]
    program_duties: List[ProgramDuty] = field(default_factory=list)
    adcvd_flags: List[ADCVDFlag] = field(default_factory=list)
    total_duty_rate: Optional[float] = None
    total_duty_amount: Optional[float] = None
    warnings: List[str] = field(default_factory=list)
    as_of_date: str = ""
    disclaimer: str = ""

    def to_dict(self) -> dict:
        return {
            "hts_code": self.hts_code,
            "country_of_origin": self.country_of_origin,
            "declared_value": self.declared_value,
            "base_duty_rate": self.base_duty_rate,
            "base_duty_amount": round(self.base_duty_amount, 2) if self.base_duty_amount is not None else None,
            "base_rate_raw": self.base_rate_raw,
            "program_duties": [
                {
                    "program": p.program,
                    "chapter99_code": p.chapter99_code,
                    "legal_basis": p.legal_basis,
                    "rate": p.rate,
                    "amount": round(p.amount, 2),
                    "notes": p.notes,
                    "source_url": p.source_url,
                }
                for p in self.program_duties
            ],
            "adcvd_flags": [
                {
                    "case_numbers": f.case_numbers,
                    "product_scope": f.product_scope,
                    "countries": f.countries,
                    "notes": f.notes,
                }
                for f in self.adcvd_flags
            ],
            "total_duty_rate": self.total_duty_rate,
            "total_duty_amount": round(self.total_duty_amount, 2) if self.total_duty_amount is not None else None,
            "warnings": self.warnings,
            "as_of_date": self.as_of_date,
            "disclaimer": self.disclaimer,
        }


class DutyCalculator:
    def __init__(self, trade_programs_path: str, adcvd_path: str):
        with open(trade_programs_path, "r", encoding="utf-8") as f:
            self._programs_data = json.load(f)
        with open(adcvd_path, "r", encoding="utf-8") as f:
            self._adcvd_data = json.load(f)

    def _matching_programs(self, hts_code: str, country: str) -> List[dict]:
        digits = hts_code.split(".")[0]
        matches = []
        for program in self._programs_data["programs"]:
            prefix_match = any(digits.startswith(p) for p in program["hts_prefixes"])
            country_match = country.upper() in program["countries"] or "*" in program["countries"]
            if prefix_match and country_match:
                matches.append(program)
        return matches

    def _matching_adcvd(self, hts_code: str, country: str) -> List[dict]:
        digits = hts_code.split(".")[0]
        matches = []
        for order in self._adcvd_data["orders"]:
            prefix_match = any(digits.startswith(p) for p in order["hts_prefixes"])
            country_match = country.upper() in order["countries"]
            if prefix_match and country_match:
                matches.append(order)
        return matches

    def calculate(
        self,
        hts_code: str,
        country_of_origin: str,
        declared_value: float,
        general_duty_rate: Optional[str] = None,
    ) -> DutyCalculationResult:
        warnings: List[str] = []

        base_rate = parse_ad_valorem_rate(general_duty_rate)
        base_amount = None
        if base_rate is not None:
            base_amount = declared_value * base_rate
        elif general_duty_rate:
            warnings.append(
                f"General duty rate {general_duty_rate!r} is a specific or compound rate "
                f"(not a simple percentage) and cannot be auto-calculated here. "
                f"Consult a customs broker or the official HTS entry for the exact amount."
            )
        else:
            warnings.append("No general duty rate was provided; base duty could not be calculated.")

        program_duties = []
        for program in self._matching_programs(hts_code, country_of_origin):
            amount = declared_value * program["additional_ad_valorem"]
            program_duties.append(
                ProgramDuty(
                    program=program["program"],
                    chapter99_code=program["chapter99_code"],
                    legal_basis=program["legal_basis"],
                    rate=program["additional_ad_valorem"],
                    amount=amount,
                    notes=program["notes"],
                    source_url=program["source_url"],
                )
            )

        adcvd_flags = [
            ADCVDFlag(
                case_numbers=order["case_numbers"],
                product_scope=order["product_scope"],
                countries=order["countries"],
                notes=order["notes"],
            )
            for order in self._matching_adcvd(hts_code, country_of_origin)
        ]
        if adcvd_flags:
            warnings.append(
                "This product/country combination matches a known AD/CVD order scope in our sample data. "
                "This is a FLAG for awareness only, not a computed rate -- verify against the official "
                "CBP ADCVD database before importing."
            )

        total_rate = None
        total_amount = None
        if base_rate is not None:
            total_rate = base_rate + sum(p.rate for p in program_duties)
            total_amount = declared_value * total_rate

        return DutyCalculationResult(
            hts_code=hts_code,
            country_of_origin=country_of_origin.upper(),
            declared_value=declared_value,
            base_duty_rate=base_rate,
            base_duty_amount=base_amount,
            base_rate_raw=general_duty_rate,
            program_duties=program_duties,
            adcvd_flags=adcvd_flags,
            total_duty_rate=total_rate,
            total_duty_amount=total_amount,
            warnings=warnings,
            as_of_date=self._programs_data.get("as_of_date", ""),
            disclaimer=self._programs_data.get("disclaimer", ""),
        )
