"""Pydantic models for RiskMesh — risk pricing and transfer marketplace."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TransactionType(str, Enum):
    SHOPPING = "shopping"
    TRAVEL = "travel"
    B2B_PURCHASE = "b2b_purchase"
    DIGITAL_SERVICE = "digital_service"
    FINANCIAL = "financial"
    LOGISTICS = "logistics"


class PolicyStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CLAIMED = "claimed"
    CANCELLED = "cancelled"


class ClaimStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    PAID = "paid"


class ClaimReason(str, Enum):
    NON_DELIVERY = "non_delivery"
    FRAUD = "fraud"
    QUALITY_ISSUE = "quality_issue"
    PRICE_DISPUTE = "price_dispute"
    OPERATIONAL_FAILURE = "operational_failure"
    COUNTERPARTY_DEFAULT = "counterparty_default"


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------

class Transaction(BaseModel):
    """A transaction submitted by an AI agent for risk assessment."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_id: str
    amount: float = Field(gt=0, description="Transaction amount in USD")
    tx_type: TransactionType
    counterparty: str
    description: str = ""
    context: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskScores(BaseModel):
    """Risk scores across five dimensions, each 0.0 to 1.0."""
    counterparty: float = Field(ge=0, le=1)
    delivery: float = Field(ge=0, le=1)
    price_volatility: float = Field(ge=0, le=1)
    fraud: float = Field(ge=0, le=1)
    operational: float = Field(ge=0, le=1)

    @property
    def composite(self) -> float:
        weights = {
            "counterparty": 0.30,
            "delivery": 0.20,
            "price_volatility": 0.15,
            "fraud": 0.25,
            "operational": 0.10,
        }
        return sum(getattr(self, k) * w for k, w in weights.items())


class RiskAssessment(BaseModel):
    """Full risk assessment for a transaction."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    transaction_id: str
    scores: RiskScores
    composite_score: float = Field(ge=0, le=1)
    expected_loss: float
    confidence: float = Field(ge=0, le=1)
    monte_carlo_iterations: int = 10_000
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InsuranceOffer(BaseModel):
    """An insurance offer generated from a risk assessment."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    assessment_id: str
    transaction_id: str
    premium: float = Field(ge=0, description="Insurance premium in USD")
    coverage: float = Field(ge=0, description="Maximum payout in USD")
    coverage_ratio: float = Field(ge=0, le=1, description="Fraction of amount covered")
    deductible: float = Field(ge=0)
    payout_conditions: list[str] = Field(default_factory=list)
    risk_margin: float = Field(ge=0)
    operational_cost: float = Field(ge=0)
    provider_id: str | None = None
    valid_until: datetime | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Policy(BaseModel):
    """An accepted insurance policy."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    offer_id: str
    transaction_id: str
    agent_id: str
    provider_id: str
    premium: float
    coverage: float
    deductible: float
    status: PolicyStatus = PolicyStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None


class Claim(BaseModel):
    """A claim filed against a policy."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    policy_id: str
    agent_id: str
    reason: ClaimReason
    claimed_amount: float = Field(ge=0)
    description: str = ""
    status: ClaimStatus = ClaimStatus.PENDING
    payout: float = 0.0
    filed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None


# ---------------------------------------------------------------------------
# Risk provider
# ---------------------------------------------------------------------------

class RiskProvider(BaseModel):
    """A risk provider offering underwriting capacity."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    capacity: float = Field(ge=0, description="Total underwriting capacity in USD")
    used_capacity: float = Field(default=0, ge=0)
    risk_appetite: float = Field(default=0.5, ge=0, le=1, description="Max composite risk score accepted")
    min_premium_rate: float = Field(default=0.01, ge=0, description="Min premium as fraction of coverage")
    specialties: list[TransactionType] = Field(default_factory=list)
    active: bool = True

    @property
    def available_capacity(self) -> float:
        return max(0, self.capacity - self.used_capacity)


# ---------------------------------------------------------------------------
# API request / response helpers
# ---------------------------------------------------------------------------

class TransactionRequest(BaseModel):
    """Inbound API request to assess a transaction."""
    agent_id: str
    amount: float = Field(gt=0)
    tx_type: TransactionType
    counterparty: str
    description: str = ""
    context: dict = Field(default_factory=dict)


class InsureRequest(BaseModel):
    """Accept an insurance offer."""
    offer_id: str
    agent_id: str


class ClaimRequest(BaseModel):
    """File a claim."""
    policy_id: str
    agent_id: str
    reason: ClaimReason
    claimed_amount: float = Field(gt=0)
    description: str = ""


class MarketStats(BaseModel):
    """Marketplace statistics."""
    total_transactions: int = 0
    total_assessments: int = 0
    total_policies: int = 0
    total_claims: int = 0
    total_premium_volume: float = 0.0
    total_coverage_volume: float = 0.0
    total_payouts: float = 0.0
    claims_ratio: float = 0.0
    avg_composite_risk: float = 0.0
    active_providers: int = 0
    total_provider_capacity: float = 0.0
    used_provider_capacity: float = 0.0
