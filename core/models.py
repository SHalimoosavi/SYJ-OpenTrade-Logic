"""
SYJ OpenTrade Logic - Core Data Models
Pure-Python, dependency-free. Runs anywhere (including Termux).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class GRIRule(str, Enum):
    GRI_1 = "GRI 1"
    GRI_2A = "GRI 2(a)"
    GRI_2B = "GRI 2(b)"
    GRI_3A = "GRI 3(a)"
    GRI_3B = "GRI 3(b)"
    GRI_3C = "GRI 3(c)"
    GRI_4 = "GRI 4"
    GRI_5A = "GRI 5(a)"
    GRI_5B = "GRI 5(b)"
    GRI_6 = "GRI 6"


@dataclass
class HTSNode:
    """A single node in the HTS tariff tree (chapter/heading/subheading)."""
    code: str                      # e.g. "8471.30"
    description: str
    level: str                     # "chapter" | "heading" | "subheading"
    keywords: List[str] = field(default_factory=list)
    legal_notes: List[str] = field(default_factory=list)
    children: List["HTSNode"] = field(default_factory=list)
    duty_rate: Optional[str] = None
    parent_code: Optional[str] = None


@dataclass
class DecisionStep:
    """One explainable step in the classification decision path."""
    node_code: str
    node_description: str
    rule_applied: GRIRule
    reasoning: str
    score: float


@dataclass
class AlternativeCode:
    code: str
    description: str
    confidence: float
    reason_not_selected: str


@dataclass
class ClassificationResult:
    product_description: str
    final_code: Optional[str]
    final_description: Optional[str]
    confidence: float
    decision_path: List[DecisionStep]
    alternatives: List[AlternativeCode]
    supporting_notes: List[str]
    duty_rate: Optional[str] = None
    is_classified: bool = False
    unresolved_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "product_description": self.product_description,
            "final_code": self.final_code,
            "final_description": self.final_description,
            "confidence": round(self.confidence, 4),
            "is_classified": self.is_classified,
            "duty_rate": self.duty_rate,
            "unresolved_reason": self.unresolved_reason,
            "decision_path": [
                {
                    "node_code": s.node_code,
                    "node_description": s.node_description,
                    "rule_applied": s.rule_applied.value,
                    "reasoning": s.reasoning,
                    "score": round(s.score, 4),
                }
                for s in self.decision_path
            ],
            "alternatives": [
                {
                    "code": a.code,
                    "description": a.description,
                    "confidence": round(a.confidence, 4),
                    "reason_not_selected": a.reason_not_selected,
                }
                for a in self.alternatives
            ],
            "supporting_notes": self.supporting_notes,
        }
