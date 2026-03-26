"""Tests for the RiskMesh REST API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import router, set_marketplace
from src.marketplace import Marketplace
from src.models import RiskProvider


@pytest.fixture
def client() -> TestClient:
    """Create a test client with a fresh marketplace (no background simulation)."""
    from fastapi import FastAPI

    mp = Marketplace(rng_seed=42)
    provider = RiskProvider(
        name="TestProvider",
        capacity=1_000_000,
        risk_appetite=0.9,
        min_premium_rate=0.005,
        specialties=[],
    )
    mp.register_provider(provider)
    set_marketplace(mp)

    # Build a minimal app without lifespan (no background simulation)
    app = FastAPI()
    app.include_router(router)

    return TestClient(app)


class TestStatsEndpoint:
    """GET /stats"""

    def test_stats_returns_valid_json(self, client: TestClient) -> None:
        response = client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert "total_transactions" in data
        assert "total_policies" in data
        assert "total_claims" in data
        assert "total_premium_volume" in data
        assert "active_providers" in data

    def test_stats_initial_values(self, client: TestClient) -> None:
        data = client.get("/stats").json()
        assert data["total_transactions"] == 0
        assert data["total_policies"] == 0
        assert data["active_providers"] == 1


class TestAssessEndpoint:
    """POST /assess"""

    def test_assess_valid_transaction(self, client: TestClient) -> None:
        payload = {
            "agent_id": "test-bot",
            "amount": 5000,
            "tx_type": "b2b_purchase",
            "counterparty": "AcmeCorp",
            "description": "Quarterly parts order",
        }
        response = client.post("/assess", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "transaction_id" in data
        assert "assessment" in data
        assert "offer" in data

        assessment = data["assessment"]
        assert 0 <= assessment["composite_score"] <= 1
        assert assessment["expected_loss"] > 0

        offer = data["offer"]
        assert offer["premium"] > 0
        assert offer["coverage"] > 0

    def test_assess_missing_fields_returns_422(self, client: TestClient) -> None:
        # Missing required fields
        payload = {"agent_id": "test-bot"}
        response = client.post("/assess", json=payload)
        assert response.status_code == 422

    def test_assess_invalid_amount_returns_422(self, client: TestClient) -> None:
        payload = {
            "agent_id": "test-bot",
            "amount": -100,
            "tx_type": "shopping",
            "counterparty": "Shop",
        }
        response = client.post("/assess", json=payload)
        assert response.status_code == 422

    def test_assess_invalid_tx_type_returns_422(self, client: TestClient) -> None:
        payload = {
            "agent_id": "test-bot",
            "amount": 1000,
            "tx_type": "invalid_type",
            "counterparty": "Shop",
        }
        response = client.post("/assess", json=payload)
        assert response.status_code == 422

    def test_assess_updates_stats(self, client: TestClient) -> None:
        payload = {
            "agent_id": "test-bot",
            "amount": 1000,
            "tx_type": "shopping",
            "counterparty": "TestShop",
            "description": "Test order",
        }
        client.post("/assess", json=payload)

        stats = client.get("/stats").json()
        assert stats["total_transactions"] == 1
        assert stats["total_assessments"] == 1


class TestInsureEndpoint:
    """POST /insure"""

    def test_accept_valid_offer(self, client: TestClient) -> None:
        # First, create an offer via /assess
        payload = {
            "agent_id": "test-bot",
            "amount": 5000,
            "tx_type": "shopping",
            "counterparty": "ShopCo",
        }
        assess_resp = client.post("/assess", json=payload).json()
        offer_id = assess_resp["offer"]["id"]

        # Accept the offer
        insure_resp = client.post(
            "/insure", json={"offer_id": offer_id, "agent_id": "test-bot"}
        )
        assert insure_resp.status_code == 200

        data = insure_resp.json()
        assert data["policy"] is not None
        assert data["policy"]["status"] == "active"

    def test_accept_nonexistent_offer(self, client: TestClient) -> None:
        resp = client.post(
            "/insure", json={"offer_id": "fake-id", "agent_id": "test-bot"}
        )
        assert resp.status_code == 404


class TestClaimEndpoint:
    """POST /claim"""

    def test_file_claim(self, client: TestClient) -> None:
        # Create offer + policy
        assess_resp = client.post("/assess", json={
            "agent_id": "bot-1",
            "amount": 5000,
            "tx_type": "b2b_purchase",
            "counterparty": "Corp",
        }).json()

        offer_id = assess_resp["offer"]["id"]
        insure_resp = client.post(
            "/insure", json={"offer_id": offer_id, "agent_id": "bot-1"}
        ).json()
        policy_id = insure_resp["policy"]["id"]

        # File claim
        claim_resp = client.post("/claim", json={
            "policy_id": policy_id,
            "agent_id": "bot-1",
            "reason": "non_delivery",
            "claimed_amount": 1000,
            "description": "Goods not received",
        })
        assert claim_resp.status_code == 200
        data = claim_resp.json()
        assert data["claim"] is not None


    def test_file_claim_nonexistent_policy(self, client: TestClient) -> None:
        resp = client.post("/claim", json={
            "policy_id": "nonexistent",
            "agent_id": "bot-1",
            "reason": "non_delivery",
            "claimed_amount": 100,
            "description": "No such policy",
        })
        assert resp.status_code == 404


class TestDashboardEndpoint:
    """GET /dashboard"""

    def test_dashboard_returns_html(self, client: TestClient) -> None:
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "RiskMesh" in response.text


class TestEventsEndpoint:
    """GET /events"""

    def test_events_returns_list(self, client: TestClient) -> None:
        response = client.get("/events")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestPoliciesEndpoint:
    """GET /policies"""

    def test_policies_returns_structure(self, client: TestClient) -> None:
        response = client.get("/policies")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "policies" in data
        assert isinstance(data["policies"], list)
