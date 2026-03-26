"""Risk marketplace — matches transactions with underwriters, tracks policies and claims."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

from .models import (
    Claim,
    ClaimRequest,
    ClaimStatus,
    InsuranceOffer,
    InsureRequest,
    MarketStats,
    Policy,
    PolicyStatus,
    RiskAssessment,
    RiskProvider,
    Transaction,
)
from .risk_engine import RiskEngine


class Marketplace:
    """Central marketplace coordinating risk assessment, pricing, and policy management."""

    def __init__(self, rng_seed: int | None = None) -> None:
        self._engine = RiskEngine(rng_seed=rng_seed)
        self._lock = threading.Lock()

        # Storage
        self.transactions: dict[str, Transaction] = {}
        self.assessments: dict[str, RiskAssessment] = {}
        self.offers: dict[str, InsuranceOffer] = {}
        self.policies: dict[str, Policy] = {}
        self.claims: dict[str, Claim] = {}
        self.providers: dict[str, RiskProvider] = {}

        # Event log for live feed
        self.event_log: list[dict] = []

    # ------------------------------------------------------------------
    # Provider management
    # ------------------------------------------------------------------

    def register_provider(self, provider: RiskProvider) -> RiskProvider:
        with self._lock:
            self.providers[provider.id] = provider
            self._log("provider_registered", f"{provider.name} joined with ${provider.capacity:,.0f} capacity")
        return provider

    # ------------------------------------------------------------------
    # Core flow
    # ------------------------------------------------------------------

    def submit_transaction(self, tx: Transaction) -> tuple[RiskAssessment, InsuranceOffer]:
        """Assess a transaction and return a risk assessment + insurance offer."""
        with self._lock:
            self.transactions[tx.id] = tx

            # 1. Risk assessment
            assessment = self._engine.assess(tx)
            self.assessments[assessment.id] = assessment

            # 2. Price insurance
            offer = self._engine.price(tx, assessment)

            # 3. Match with best provider
            provider = self._match_provider(tx, assessment, offer)
            if provider:
                offer.provider_id = provider.id

            offer.valid_until = datetime.now(timezone.utc) + timedelta(minutes=5)
            self.offers[offer.id] = offer

            self._log(
                "assessment",
                f"Agent {tx.agent_id} | ${tx.amount:.0f} {tx.tx_type.value} | "
                f"risk={assessment.composite_score:.2f} | premium=${offer.premium:.2f}",
            )
        return assessment, offer

    def accept_offer(self, req: InsureRequest) -> Policy | None:
        """Agent accepts an insurance offer, creating a policy."""
        with self._lock:
            offer = self.offers.get(req.offer_id)
            if not offer:
                return None

            # Check validity
            if offer.valid_until and datetime.now(timezone.utc) > offer.valid_until:
                self._log("offer_expired", f"Offer {offer.id} expired")
                return None

            provider_id = offer.provider_id or "pool"

            # Allocate provider capacity
            if offer.provider_id and offer.provider_id in self.providers:
                prov = self.providers[offer.provider_id]
                if prov.available_capacity < offer.coverage:
                    self._log("capacity_exceeded", f"Provider {prov.name} lacks capacity")
                    return None
                prov.used_capacity += offer.coverage

            # Track exposure
            tx = self.transactions.get(offer.transaction_id)
            if tx:
                self._engine.record_exposure(tx.counterparty, offer.coverage)

            policy = Policy(
                offer_id=offer.id,
                transaction_id=offer.transaction_id,
                agent_id=req.agent_id,
                provider_id=provider_id,
                premium=offer.premium,
                coverage=offer.coverage,
                deductible=offer.deductible,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            self.policies[policy.id] = policy

            self._log(
                "policy_created",
                f"Policy {policy.id} | agent={req.agent_id} | "
                f"premium=${policy.premium:.2f} coverage=${policy.coverage:.2f}",
            )
            return policy

    def file_claim(self, req: ClaimRequest) -> Claim | None:
        """File a claim against a policy."""
        with self._lock:
            policy = self.policies.get(req.policy_id)
            if not policy or policy.status != PolicyStatus.ACTIVE:
                return None
            if policy.agent_id != req.agent_id:
                return None

            claim = Claim(
                policy_id=req.policy_id,
                agent_id=req.agent_id,
                reason=req.reason,
                claimed_amount=req.claimed_amount,
                description=req.description,
            )

            # Auto-adjudicate (simplified)
            payout = self._adjudicate(claim, policy)
            claim.payout = payout
            claim.status = ClaimStatus.APPROVED if payout > 0 else ClaimStatus.DENIED
            claim.resolved_at = datetime.now(timezone.utc)

            if payout > 0:
                policy.status = PolicyStatus.CLAIMED
                # Release provider capacity
                if policy.provider_id in self.providers:
                    prov = self.providers[policy.provider_id]
                    prov.used_capacity = max(0, prov.used_capacity - policy.coverage)

            self.claims[claim.id] = claim
            self._log(
                "claim_filed",
                f"Claim {claim.id} | policy={req.policy_id} | "
                f"reason={req.reason.value} | payout=${payout:.2f} | {claim.status.value}",
            )
            return claim

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_active_policies(self) -> list[Policy]:
        return [p for p in self.policies.values() if p.status == PolicyStatus.ACTIVE]

    def get_stats(self) -> MarketStats:
        total_premiums = sum(p.premium for p in self.policies.values())
        total_coverage = sum(p.coverage for p in self.policies.values())
        total_payouts = sum(c.payout for c in self.claims.values())
        total_policies = len(self.policies)
        total_claims = len(self.claims)
        claims_ratio = total_claims / total_policies if total_policies > 0 else 0

        risk_scores = [a.composite_score for a in self.assessments.values()]
        avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0

        active_provs = [p for p in self.providers.values() if p.active]

        return MarketStats(
            total_transactions=len(self.transactions),
            total_assessments=len(self.assessments),
            total_policies=total_policies,
            total_claims=total_claims,
            total_premium_volume=round(total_premiums, 2),
            total_coverage_volume=round(total_coverage, 2),
            total_payouts=round(total_payouts, 2),
            claims_ratio=round(claims_ratio, 4),
            avg_composite_risk=round(avg_risk, 4),
            active_providers=len(active_provs),
            total_provider_capacity=round(sum(p.capacity for p in active_provs), 2),
            used_provider_capacity=round(sum(p.used_capacity for p in active_provs), 2),
        )

    def recent_events(self, n: int = 50) -> list[dict]:
        return list(reversed(self.event_log[-n:]))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _match_provider(
        self,
        tx: Transaction,
        assessment: RiskAssessment,
        offer: InsuranceOffer,
    ) -> RiskProvider | None:
        """Find the best provider for this transaction."""
        candidates: list[tuple[float, RiskProvider]] = []
        for prov in self.providers.values():
            if not prov.active:
                continue
            if prov.available_capacity < offer.coverage:
                continue
            if assessment.composite_score > prov.risk_appetite:
                continue
            # Prefer specialists
            score = 0.0
            if tx.tx_type in prov.specialties:
                score += 1.0
            # Prefer providers with more capacity
            score += prov.available_capacity / max(prov.capacity, 1)
            candidates.append((score, prov))

        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    @staticmethod
    def _adjudicate(claim: Claim, policy: Policy) -> float:
        """Simple auto-adjudication: approve if claimed amount is within coverage."""
        if claim.claimed_amount <= 0:
            return 0.0
        # Apply deductible
        eligible = max(0, claim.claimed_amount - policy.deductible)
        # Cap at coverage
        payout = min(eligible, policy.coverage)
        return round(payout, 2)

    def _log(self, event_type: str, message: str) -> None:
        self.event_log.append({
            "type": event_type,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Keep log bounded
        if len(self.event_log) > 500:
            self.event_log = self.event_log[-500:]
