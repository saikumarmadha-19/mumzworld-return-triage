from typing import List, Literal
from pydantic import BaseModel, Field


Decision = Literal[
    "refund",
    "exchange",
    "store_credit",
    "escalate",
    "reject",
    "uncertain"
]

Language = Literal["en", "ar", "mixed", "unknown"]


class TriageResult(BaseModel):
    intent: str = Field(..., description="Customer intent, e.g. return_refund, exchange, safety_complaint")
    decision: Decision
    confidence: float = Field(..., ge=0, le=1)
    language_detected: Language
    reason_category: str
    policy_basis: List[str]
    missing_information: List[str]
    risk_flags: List[str]
    customer_reply_en: str
    customer_reply_ar: str