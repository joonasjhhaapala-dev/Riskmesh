"""Tests for the RiskMesh risk pricing engine."""

from __future__ import annotations

import pytest

from src.models import Transaction, TransactionType
from src.risk_engine import RiskEngine


class TestRiskScores:
    """Verify risk scores are bounded and well-formed."""

    def test_scores_between_zero_and_one(
        self, engine: RiskEngine, sample_transaction: Transaction
    ) -> None:
        assessment = engine.assess(sample_transaction)
        scores = assessment.scores

        for dim in ("counterparty", "delivery", "price_volatility", "fraud", "operational"):
            value = getattr(scores, dim)
            assert 0.0 <= value <= 1.0, f"{dim} score {value} out of range [0, 1]"

    def test_composite_score_between_zero_and_one(
        self, engine: RiskEngine, sample_transaction: Transaction
    ) -> None:
        assessment = engine.assess(sample_transaction)
        assert 0.0 <= assessment.composite_score <= 1.0

    def test_confidence_between_zero_and_one(
        self, engine: RiskEngine, sample_transaction: Transaction
    ) -> None:
        assessment = engine.assess(sample_transaction)
        assert 0.0 <= assessment.confidence <= 1.0


class TestPremiumPricing:
    """Verify premium pricing logic."""

    def test_premium_is_positive(
        self, engine: RiskEngine, sample_transaction: Transaction
    ) -> None:
        assessment = engine.assess(sample_transaction)
        offer = engine.price(sample_transaction, assessment)
        assert offer.premium > 0

    def test_premium_less_than_transaction_amount(
        self, engine: RiskEngine, sample_transaction: Transaction
    ) -> None:
        assessment = engine.assess(sample_transaction)
        offer = engine.price(sample_transaction, assessment)
        assert offer.premium < sample_transaction.amount

    def test_coverage_does_not_exceed_amount(
        self, engine: RiskEngine, sample_transaction: Transaction
    ) -> None:
        assessment = engine.assess(sample_transaction)
        offer = engine.price(sample_transaction, assessment)
        assert offer.coverage <= sample_transaction.amount

    def test_coverage_ratio_bounded(
        self, engine: RiskEngine, sample_transaction: Transaction
    ) -> None:
        assessment = engine.assess(sample_transaction)
        offer = engine.price(sample_transaction, assessment)
        assert 0.50 <= offer.coverage_ratio <= 0.95

    def test_higher_risk_gets_higher_premium(self, engine: RiskEngine) -> None:
        """Financial transactions with large amounts should produce higher premiums
        than small shopping transactions."""
        low = Transaction(
            agent_id="a1", amount=100, tx_type=TransactionType.SHOPPING,
            counterparty="Safe", description="Small purchase",
        )
        high = Transaction(
            agent_id="a2", amount=100_000, tx_type=TransactionType.FINANCIAL,
            counterparty="Risky", description="Large derivative",
        )

        a_low = engine.assess(low)
        o_low = engine.price(low, a_low)

        a_high = engine.assess(high)
        o_high = engine.price(high, a_high)

        assert o_high.premium > o_low.premium


class TestMonteCarloConvergence:
    """Verify Monte Carlo simulation produces stable results."""

    def test_two_runs_give_similar_results(self) -> None:
        tx = Transaction(
            agent_id="convergence-test",
            amount=10_000,
            tx_type=TransactionType.B2B_PURCHASE,
            counterparty="StableCorp",
            description="Convergence check",
        )

        engine_a = RiskEngine(rng_seed=100)
        engine_b = RiskEngine(rng_seed=100)

        a1 = engine_a.assess(tx)
        a2 = engine_b.assess(tx)

        # Same seed should give identical results
        assert a1.composite_score == a2.composite_score
        assert a1.expected_loss == a2.expected_loss

    def test_different_seeds_give_reasonable_range(self) -> None:
        tx = Transaction(
            agent_id="range-test",
            amount=5_000,
            tx_type=TransactionType.SHOPPING,
            counterparty="TestCo",
            description="Range check",
        )

        results = []
        for seed in range(10):
            engine = RiskEngine(rng_seed=seed)
            assessment = engine.assess(tx)
            results.append(assessment.expected_loss)

        # All expected losses should be positive and within a reasonable range
        for el in results:
            assert el > 0
            assert el < tx.amount


class TestAllTransactionTypes:
    """Verify all transaction types produce valid assessments."""

    @pytest.mark.parametrize("tx_type", list(TransactionType))
    def test_transaction_type_produces_valid_assessment(
        self, engine: RiskEngine, tx_type: TransactionType
    ) -> None:
        tx = Transaction(
            agent_id="type-test",
            amount=5_000,
            tx_type=tx_type,
            counterparty="GenericCorp",
            description=f"Test for {tx_type.value}",
        )
        assessment = engine.assess(tx)

        assert 0.0 <= assessment.composite_score <= 1.0
        assert assessment.expected_loss > 0
        assert assessment.expected_loss < tx.amount
        assert 0.0 <= assessment.confidence <= 1.0
        assert assessment.monte_carlo_iterations > 0

    @pytest.mark.parametrize("tx_type", list(TransactionType))
    def test_transaction_type_produces_valid_offer(
        self, engine: RiskEngine, tx_type: TransactionType
    ) -> None:
        tx = Transaction(
            agent_id="type-test",
            amount=5_000,
            tx_type=tx_type,
            counterparty="GenericCorp",
            description=f"Test for {tx_type.value}",
        )
        assessment = engine.assess(tx)
        offer = engine.price(tx, assessment)

        assert offer.premium > 0
        assert offer.premium < tx.amount
        assert offer.coverage > 0
        assert offer.coverage <= tx.amount
        assert len(offer.payout_conditions) > 0
