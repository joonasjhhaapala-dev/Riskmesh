"""Tests for the RiskMesh marketplace."""

from __future__ import annotations

import pytest

from src.marketplace import Marketplace
from src.models import (
    ClaimReason,
    ClaimRequest,
    ClaimStatus,
    InsureRequest,
    PolicyStatus,
    RiskProvider,
    Transaction,
    TransactionType,
)


class TestProviderRegistration:
    """Verify provider registration."""

    def test_register_provider(self, marketplace: Marketplace) -> None:
        # conftest already registered one provider
        assert len(marketplace.providers) == 1

    def test_register_multiple_providers(self) -> None:
        mp = Marketplace(rng_seed=1)
        p1 = RiskProvider(name="Provider A", capacity=500_000, risk_appetite=0.7)
        p2 = RiskProvider(name="Provider B", capacity=300_000, risk_appetite=0.5)

        mp.register_provider(p1)
        mp.register_provider(p2)

        assert len(mp.providers) == 2
        assert p1.id in mp.providers
        assert p2.id in mp.providers

    def test_provider_logged_in_events(self, marketplace: Marketplace) -> None:
        events = marketplace.recent_events(10)
        assert any("joined" in e["message"] for e in events)


class TestTransactionAssessment:
    """Verify the submit_transaction flow."""

    def test_submit_transaction(
        self, marketplace: Marketplace, sample_transaction: Transaction
    ) -> None:
        assessment, offer = marketplace.submit_transaction(sample_transaction)

        assert assessment is not None
        assert offer is not None
        assert assessment.transaction_id == sample_transaction.id
        assert offer.transaction_id == sample_transaction.id

    def test_assessment_stored(
        self, marketplace: Marketplace, sample_transaction: Transaction
    ) -> None:
        assessment, _ = marketplace.submit_transaction(sample_transaction)
        assert assessment.id in marketplace.assessments

    def test_offer_stored(
        self, marketplace: Marketplace, sample_transaction: Transaction
    ) -> None:
        _, offer = marketplace.submit_transaction(sample_transaction)
        assert offer.id in marketplace.offers

    def test_transaction_stored(
        self, marketplace: Marketplace, sample_transaction: Transaction
    ) -> None:
        marketplace.submit_transaction(sample_transaction)
        assert sample_transaction.id in marketplace.transactions

    def test_offer_has_valid_until(
        self, marketplace: Marketplace, sample_transaction: Transaction
    ) -> None:
        _, offer = marketplace.submit_transaction(sample_transaction)
        assert offer.valid_until is not None


class TestPolicyCreation:
    """Verify accepting an offer creates a policy."""

    def test_accept_offer_creates_policy(
        self, marketplace: Marketplace, sample_transaction: Transaction
    ) -> None:
        _, offer = marketplace.submit_transaction(sample_transaction)
        req = InsureRequest(offer_id=offer.id, agent_id=sample_transaction.agent_id)
        policy = marketplace.accept_offer(req)

        assert policy is not None
        assert policy.status == PolicyStatus.ACTIVE
        assert policy.premium == offer.premium
        assert policy.coverage == offer.coverage

    def test_accept_invalid_offer_returns_none(
        self, marketplace: Marketplace
    ) -> None:
        req = InsureRequest(offer_id="nonexistent", agent_id="test")
        policy = marketplace.accept_offer(req)
        assert policy is None

    def test_policy_stored(
        self, marketplace: Marketplace, sample_transaction: Transaction
    ) -> None:
        _, offer = marketplace.submit_transaction(sample_transaction)
        req = InsureRequest(offer_id=offer.id, agent_id=sample_transaction.agent_id)
        policy = marketplace.accept_offer(req)

        assert policy is not None
        assert policy.id in marketplace.policies

    def test_active_policies_list(
        self, marketplace: Marketplace, sample_transaction: Transaction
    ) -> None:
        _, offer = marketplace.submit_transaction(sample_transaction)
        req = InsureRequest(offer_id=offer.id, agent_id=sample_transaction.agent_id)
        marketplace.accept_offer(req)

        active = marketplace.get_active_policies()
        assert len(active) == 1
        assert active[0].status == PolicyStatus.ACTIVE


class TestClaimFiling:
    """Verify claim filing and adjudication."""

    def _create_policy(
        self, marketplace: Marketplace, tx: Transaction
    ) -> str:
        """Helper: submit, insure, return policy_id."""
        _, offer = marketplace.submit_transaction(tx)
        req = InsureRequest(offer_id=offer.id, agent_id=tx.agent_id)
        policy = marketplace.accept_offer(req)
        assert policy is not None
        return policy.id

    def test_file_claim_approved(
        self, marketplace: Marketplace, sample_transaction: Transaction
    ) -> None:
        policy_id = self._create_policy(marketplace, sample_transaction)
        policy = marketplace.policies[policy_id]

        claim_req = ClaimRequest(
            policy_id=policy_id,
            agent_id=sample_transaction.agent_id,
            reason=ClaimReason.NON_DELIVERY,
            claimed_amount=policy.coverage * 0.5,
            description="Goods never arrived",
        )
        claim = marketplace.file_claim(claim_req)

        assert claim is not None
        assert claim.status == ClaimStatus.APPROVED
        assert claim.payout > 0

    def test_claim_payout_capped_at_coverage(
        self, marketplace: Marketplace, sample_transaction: Transaction
    ) -> None:
        policy_id = self._create_policy(marketplace, sample_transaction)
        policy = marketplace.policies[policy_id]

        claim_req = ClaimRequest(
            policy_id=policy_id,
            agent_id=sample_transaction.agent_id,
            reason=ClaimReason.FRAUD,
            claimed_amount=policy.coverage * 10,  # Much more than coverage
            description="Massive fraud",
        )
        claim = marketplace.file_claim(claim_req)

        assert claim is not None
        assert claim.payout <= policy.coverage

    def test_claim_on_inactive_policy_returns_none(
        self, marketplace: Marketplace, sample_transaction: Transaction
    ) -> None:
        policy_id = self._create_policy(marketplace, sample_transaction)

        # File first claim — this marks the policy as claimed
        policy = marketplace.policies[policy_id]
        claim_req = ClaimRequest(
            policy_id=policy_id,
            agent_id=sample_transaction.agent_id,
            reason=ClaimReason.NON_DELIVERY,
            claimed_amount=policy.coverage * 0.5,
            description="First claim",
        )
        marketplace.file_claim(claim_req)

        # Second claim on same policy should fail
        claim_req2 = ClaimRequest(
            policy_id=policy_id,
            agent_id=sample_transaction.agent_id,
            reason=ClaimReason.QUALITY_ISSUE,
            claimed_amount=100,
            description="Second claim",
        )
        result = marketplace.file_claim(claim_req2)
        assert result is None

    def test_claim_wrong_agent_returns_none(
        self, marketplace: Marketplace, sample_transaction: Transaction
    ) -> None:
        policy_id = self._create_policy(marketplace, sample_transaction)

        claim_req = ClaimRequest(
            policy_id=policy_id,
            agent_id="wrong-agent",
            reason=ClaimReason.NON_DELIVERY,
            claimed_amount=100,
            description="Unauthorized claim",
        )
        result = marketplace.file_claim(claim_req)
        assert result is None


class TestMarketStats:
    """Verify statistics computation."""

    def test_stats_after_transaction(
        self, marketplace: Marketplace, sample_transaction: Transaction
    ) -> None:
        marketplace.submit_transaction(sample_transaction)
        stats = marketplace.get_stats()

        assert stats.total_transactions == 1
        assert stats.total_assessments == 1
        assert stats.active_providers == 1

    def test_stats_after_policy(
        self, marketplace: Marketplace, sample_transaction: Transaction
    ) -> None:
        _, offer = marketplace.submit_transaction(sample_transaction)
        req = InsureRequest(offer_id=offer.id, agent_id=sample_transaction.agent_id)
        marketplace.accept_offer(req)

        stats = marketplace.get_stats()
        assert stats.total_policies == 1
        assert stats.total_premium_volume > 0
        assert stats.total_coverage_volume > 0

    def test_stats_empty_marketplace(self) -> None:
        mp = Marketplace(rng_seed=1)
        stats = mp.get_stats()

        assert stats.total_transactions == 0
        assert stats.total_policies == 0
        assert stats.total_claims == 0
        assert stats.claims_ratio == 0.0
        assert stats.avg_composite_risk == 0.0


class TestEventLog:
    """Verify event logging."""

    def test_events_recorded(
        self, marketplace: Marketplace, sample_transaction: Transaction
    ) -> None:
        marketplace.submit_transaction(sample_transaction)
        events = marketplace.recent_events(10)

        # Should have at least provider_registered + assessment events
        assert len(events) >= 2

    def test_events_ordered_newest_first(
        self, marketplace: Marketplace, sample_transaction: Transaction
    ) -> None:
        marketplace.submit_transaction(sample_transaction)
        events = marketplace.recent_events(10)

        # Most recent event should be the assessment
        assert events[0]["type"] == "assessment"
