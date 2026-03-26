"""Core risk pricing engine using Monte Carlo simulation and beta distributions."""

from __future__ import annotations

import numpy as np
from scipy import stats

from .models import (
    InsuranceOffer,
    RiskAssessment,
    RiskScores,
    Transaction,
    TransactionType,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MC_ITERATIONS = 10_000

# Base risk parameters per transaction type  (alpha, beta for Beta distribution)
# Higher alpha relative to beta  =>  higher expected probability of loss
BASE_RISK_PARAMS: dict[TransactionType, dict[str, tuple[float, float]]] = {
    TransactionType.SHOPPING: {
        "counterparty": (2, 8),
        "delivery": (3, 7),
        "price_volatility": (1, 9),
        "fraud": (2, 8),
        "operational": (1, 9),
    },
    TransactionType.TRAVEL: {
        "counterparty": (2, 8),
        "delivery": (2, 6),
        "price_volatility": (3, 6),
        "fraud": (1.5, 8),
        "operational": (2, 7),
    },
    TransactionType.B2B_PURCHASE: {
        "counterparty": (3, 7),
        "delivery": (3, 7),
        "price_volatility": (2, 7),
        "fraud": (2, 9),
        "operational": (2, 7),
    },
    TransactionType.DIGITAL_SERVICE: {
        "counterparty": (2, 9),
        "delivery": (1, 9),
        "price_volatility": (1, 9),
        "fraud": (3, 7),
        "operational": (2, 8),
    },
    TransactionType.FINANCIAL: {
        "counterparty": (3, 6),
        "delivery": (2, 8),
        "price_volatility": (4, 5),
        "fraud": (3, 6),
        "operational": (2, 7),
    },
    TransactionType.LOGISTICS: {
        "counterparty": (2, 7),
        "delivery": (4, 6),
        "price_volatility": (2, 8),
        "fraud": (1.5, 8),
        "operational": (3, 6),
    },
}

# Risk margin and operational cost factors
BASE_RISK_MARGIN = 0.35          # 35 % risk margin
BASE_OPERATIONAL_COST = 0.10     # 10 % operational loading
CONCENTRATION_FACTOR = 0.05      # extra charge per 10 % portfolio concentration
MIN_PREMIUM = 0.50               # absolute floor in USD


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RiskEngine:
    """Prices risk for AI-agent transactions using Monte Carlo simulation."""

    def __init__(self, rng_seed: int | None = None) -> None:
        self._rng = np.random.default_rng(rng_seed)
        # Track portfolio for concentration risk
        self._counterparty_exposure: dict[str, float] = {}
        self._total_exposure: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assess(self, tx: Transaction) -> RiskAssessment:
        """Run a full risk assessment for *tx*."""
        scores = self._score(tx)
        composite = scores.composite
        expected_loss = self._monte_carlo_expected_loss(tx, scores)
        confidence = self._confidence(tx)

        return RiskAssessment(
            transaction_id=tx.id,
            scores=scores,
            composite_score=round(composite, 4),
            expected_loss=round(expected_loss, 2),
            confidence=round(confidence, 4),
            monte_carlo_iterations=MC_ITERATIONS,
        )

    def price(self, tx: Transaction, assessment: RiskAssessment) -> InsuranceOffer:
        """Generate an insurance offer from an assessment."""
        el = assessment.expected_loss
        composite = assessment.composite_score

        # Coverage ratio depends on risk — higher risk => lower coverage
        coverage_ratio = max(0.50, min(0.95, 1.0 - composite * 0.5))
        coverage = round(tx.amount * coverage_ratio, 2)

        # Concentration risk surcharge
        conc = self._concentration_risk(tx.counterparty)
        risk_margin = BASE_RISK_MARGIN + conc
        operational_cost = BASE_OPERATIONAL_COST

        # Premium = E[L] * (1 + risk_margin) * (1 + op_cost)
        premium = el * (1 + risk_margin) * (1 + operational_cost)
        premium = round(max(premium, MIN_PREMIUM), 2)

        # Deductible — proportional to amount and risk
        deductible = round(tx.amount * composite * 0.10, 2)

        # Payout conditions
        conditions = self._payout_conditions(tx, assessment.scores)

        return InsuranceOffer(
            assessment_id=assessment.id,
            transaction_id=tx.id,
            premium=premium,
            coverage=coverage,
            coverage_ratio=round(coverage_ratio, 4),
            deductible=deductible,
            payout_conditions=conditions,
            risk_margin=round(risk_margin, 4),
            operational_cost=round(operational_cost, 4),
        )

    def record_exposure(self, counterparty: str, amount: float) -> None:
        """Track exposure for concentration risk."""
        self._counterparty_exposure[counterparty] = (
            self._counterparty_exposure.get(counterparty, 0) + amount
        )
        self._total_exposure += amount

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _score(self, tx: Transaction) -> RiskScores:
        """Compute risk scores using Beta-distribution sampling."""
        params = BASE_RISK_PARAMS.get(tx.tx_type, BASE_RISK_PARAMS[TransactionType.SHOPPING])
        scores: dict[str, float] = {}

        for dim, (a, b) in params.items():
            # Adjust alpha for amount — larger amounts increase risk slightly
            amount_factor = min(tx.amount / 10_000, 1.0) * 0.5
            adj_a = a + amount_factor

            # Sample from Beta and take the mean of N draws for stability
            samples = stats.beta.rvs(adj_a, b, size=500, random_state=self._rng.integers(0, 2**31))
            scores[dim] = float(np.mean(samples))

        # Clamp to [0, 1]
        scores = {k: max(0.0, min(1.0, v)) for k, v in scores.items()}
        return RiskScores(**scores)

    def _monte_carlo_expected_loss(self, tx: Transaction, scores: RiskScores) -> float:
        """Monte Carlo simulation of expected loss."""
        composite = scores.composite

        # Probability of loss event ~ Beta(composite * 10, (1-composite) * 10)
        a = max(composite * 10, 0.5)
        b = max((1 - composite) * 10, 0.5)
        prob_samples = stats.beta.rvs(a, b, size=MC_ITERATIONS, random_state=self._rng.integers(0, 2**31))

        # Severity ~ Beta distribution centered around composite score
        sev_a = max(composite * 5, 0.5)
        sev_b = max((1 - composite) * 5, 0.5)
        severity_samples = stats.beta.rvs(sev_a, sev_b, size=MC_ITERATIONS, random_state=self._rng.integers(0, 2**31))

        # Loss = prob * severity * amount  (each iteration)
        losses = prob_samples * severity_samples * tx.amount

        # Expected loss = mean of simulated losses
        return float(np.mean(losses))

    def _confidence(self, tx: Transaction) -> float:
        """Confidence in the assessment (0-1). More context => higher."""
        base = 0.60
        if tx.description:
            base += 0.10
        if tx.context:
            base += min(len(tx.context) * 0.05, 0.20)
        return min(base, 0.95)

    def _concentration_risk(self, counterparty: str) -> float:
        """Extra risk margin if counterparty represents large share of portfolio."""
        if self._total_exposure <= 0:
            return 0.0
        share = self._counterparty_exposure.get(counterparty, 0) / self._total_exposure
        # 5 % surcharge per 10 % portfolio share
        return share * CONCENTRATION_FACTOR * 10

    @staticmethod
    def _payout_conditions(tx: Transaction, scores: RiskScores) -> list[str]:
        """Generate human-readable payout conditions."""
        conditions: list[str] = []
        if scores.counterparty > 0.3:
            conditions.append("Counterparty default or insolvency")
        if scores.delivery > 0.3:
            conditions.append("Non-delivery or late delivery beyond SLA")
        if scores.price_volatility > 0.3:
            conditions.append("Price movement exceeding 15% from agreed price")
        if scores.fraud > 0.3:
            conditions.append("Verified fraudulent activity by counterparty")
        if scores.operational > 0.3:
            conditions.append("System or operational failure causing loss")
        if not conditions:
            conditions.append("Material breach of transaction terms")
        return conditions
