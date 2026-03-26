"""Shared test fixtures for RiskMesh tests."""

from __future__ import annotations

import pytest

from src.marketplace import Marketplace
from src.models import (
    RiskProvider,
    Transaction,
    TransactionType,
)
from src.risk_engine import RiskEngine


@pytest.fixture
def engine() -> RiskEngine:
    """Return a seeded RiskEngine for deterministic tests."""
    return RiskEngine(rng_seed=42)


@pytest.fixture
def marketplace() -> Marketplace:
    """Return a seeded Marketplace with one registered provider."""
    mp = Marketplace(rng_seed=42)
    provider = RiskProvider(
        name="TestProvider",
        capacity=1_000_000,
        risk_appetite=0.9,
        min_premium_rate=0.005,
        specialties=[TransactionType.SHOPPING, TransactionType.FINANCIAL],
    )
    mp.register_provider(provider)
    return mp


@pytest.fixture
def sample_transaction() -> Transaction:
    """Return a basic sample transaction."""
    return Transaction(
        agent_id="test-agent-001",
        amount=5_000.0,
        tx_type=TransactionType.B2B_PURCHASE,
        counterparty="AcmeCorp",
        description="Quarterly parts order",
    )


@pytest.fixture
def high_risk_transaction() -> Transaction:
    """Return a high-amount financial transaction (higher risk)."""
    return Transaction(
        agent_id="test-agent-002",
        amount=90_000.0,
        tx_type=TransactionType.FINANCIAL,
        counterparty="UnknownBank",
        description="Large cross-border transfer",
    )


@pytest.fixture
def low_risk_transaction() -> Transaction:
    """Return a small shopping transaction (lower risk)."""
    return Transaction(
        agent_id="test-agent-003",
        amount=100.0,
        tx_type=TransactionType.SHOPPING,
        counterparty="TrustedStore",
        description="Office supplies restock",
    )
