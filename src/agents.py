"""Simulated AI agents that generate transactions and interact with the marketplace."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .models import (
    ClaimReason,
    ClaimRequest,
    InsureRequest,
    Transaction,
    TransactionType,
)
from .marketplace import Marketplace


# ---------------------------------------------------------------------------
# Agent configuration
# ---------------------------------------------------------------------------

AGENT_NAMES = [
    "ShopBot-Alpha", "TravelAI-1", "ProcureNet", "DigitalBuyer", "FinanceBot",
    "LogiAgent", "SmartShop-2", "JetSetAI", "B2B-Nexus", "CyberPay",
    "FreightMind", "RetailBot-3", "BookingAI", "SupplyChain-X", "PayFlow",
    "CargoSense", "DealHunter", "TripWise", "VendorLink", "OptiTrade",
]

COUNTERPARTIES = [
    "AmazoCorp", "GlobalTech Ltd", "SkyWay Airlines", "NeoMart",
    "DataVault Inc", "TransGlobal Shipping", "EcoGoods", "CloudServe",
    "MetalWorks GmbH", "FreshFoods Co", "ByteStream", "StarLogistics",
    "QuantumParts", "GreenEnergy SA", "SafeHaven Bank", "SwiftCargo",
]

TX_DESCRIPTIONS = {
    TransactionType.SHOPPING: [
        "Bulk electronics purchase", "Office supplies order", "Raw materials restock",
        "Consumer electronics bundle", "Seasonal inventory buy",
    ],
    TransactionType.TRAVEL: [
        "Executive flight booking", "Conference travel package", "Multi-city tour",
        "Last-minute business trip", "Team retreat arrangement",
    ],
    TransactionType.B2B_PURCHASE: [
        "Industrial equipment order", "Software license bulk buy", "Component supply contract",
        "Quarterly materials procurement", "Service contract renewal",
    ],
    TransactionType.DIGITAL_SERVICE: [
        "Cloud infrastructure upgrade", "SaaS annual subscription", "API access tier upgrade",
        "Data processing pipeline", "CDN service expansion",
    ],
    TransactionType.FINANCIAL: [
        "Currency exchange operation", "Investment portfolio rebalance", "Escrow deposit",
        "Cross-border payment", "Derivatives hedge",
    ],
    TransactionType.LOGISTICS: [
        "International freight shipment", "Warehousing contract", "Last-mile delivery batch",
        "Cold-chain transport", "Hazmat cargo movement",
    ],
}

AMOUNT_RANGES: dict[TransactionType, tuple[float, float]] = {
    TransactionType.SHOPPING: (50, 5_000),
    TransactionType.TRAVEL: (200, 15_000),
    TransactionType.B2B_PURCHASE: (1_000, 50_000),
    TransactionType.DIGITAL_SERVICE: (100, 10_000),
    TransactionType.FINANCIAL: (500, 100_000),
    TransactionType.LOGISTICS: (300, 25_000),
}


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

@dataclass
class SimAgent:
    """A simulated AI agent in the marketplace."""
    id: str
    name: str
    risk_tolerance: float = 0.5        # 0 = very risk-averse, 1 = risk-seeking
    budget: float = 100_000.0
    preferred_types: list[TransactionType] = field(default_factory=list)
    active_policies: list[str] = field(default_factory=list)
    total_premiums_paid: float = 0.0
    total_claims_received: float = 0.0
    transactions_count: int = 0

    def generate_transaction(self) -> Transaction:
        """Create a random plausible transaction."""
        tx_type = random.choice(self.preferred_types) if self.preferred_types else random.choice(list(TransactionType))
        lo, hi = AMOUNT_RANGES[tx_type]
        amount = round(random.uniform(lo, hi), 2)
        counterparty = random.choice(COUNTERPARTIES)
        description = random.choice(TX_DESCRIPTIONS[tx_type])

        context: dict = {}
        if random.random() > 0.5:
            context["urgency"] = random.choice(["low", "medium", "high"])
        if random.random() > 0.6:
            context["repeat_customer"] = random.choice([True, False])

        return Transaction(
            agent_id=self.id,
            amount=amount,
            tx_type=tx_type,
            counterparty=counterparty,
            description=description,
            context=context,
        )

    def decide_insure(self, premium: float, coverage: float, composite_risk: float) -> bool:
        """Decide whether to accept an insurance offer."""
        # Cost-benefit: ratio of premium to coverage
        cost_ratio = premium / coverage if coverage > 0 else 1.0

        # Risk-averse agents insure more; risk-seeking agents only insure high-risk
        threshold = 0.15 - (self.risk_tolerance * 0.10)  # 0.05 to 0.15 cost ratio threshold

        # Always insure if risk is high and we're not super risk-seeking
        if composite_risk > 0.5 and self.risk_tolerance < 0.8:
            return True

        # Insure if the cost ratio is acceptable
        if cost_ratio < threshold:
            return True

        # Random factor — sometimes agents just insure anyway
        return random.random() < (1 - self.risk_tolerance) * 0.3

    def decide_claim(self) -> bool:
        """Randomly decide if a claim event occurs (~8 % of policies)."""
        return random.random() < 0.08

    def pick_claim_reason(self) -> ClaimReason:
        return random.choice(list(ClaimReason))


def create_agents(n: int = 20) -> list[SimAgent]:
    """Create *n* diverse simulated agents."""
    agents: list[SimAgent] = []
    for i in range(n):
        name = AGENT_NAMES[i % len(AGENT_NAMES)]
        if i >= len(AGENT_NAMES):
            name = f"{name}-{i // len(AGENT_NAMES)}"

        # Assign 1-3 preferred transaction types
        num_prefs = random.randint(1, 3)
        prefs = random.sample(list(TransactionType), num_prefs)

        agent = SimAgent(
            id=f"agent-{i:03d}",
            name=name,
            risk_tolerance=round(random.uniform(0.1, 0.9), 2),
            budget=round(random.uniform(50_000, 500_000), 2),
            preferred_types=prefs,
        )
        agents.append(agent)
    return agents


def run_agent_cycle(agent: SimAgent, marketplace: Marketplace) -> dict | None:
    """Run one transaction cycle for an agent. Returns event info or None."""
    # 1. Generate a transaction
    tx = agent.generate_transaction()

    # 2. Submit for assessment
    assessment, offer = marketplace.submit_transaction(tx)
    agent.transactions_count += 1

    # 3. Decide whether to insure
    if agent.decide_insure(offer.premium, offer.coverage, assessment.composite_score):
        req = InsureRequest(offer_id=offer.id, agent_id=agent.id)
        policy = marketplace.accept_offer(req)
        if policy:
            agent.active_policies.append(policy.id)
            agent.total_premiums_paid += policy.premium

            result = {
                "agent": agent.name,
                "action": "insured",
                "tx_type": tx.tx_type.value,
                "amount": tx.amount,
                "risk": assessment.composite_score,
                "premium": offer.premium,
                "coverage": offer.coverage,
            }

            # 4. Check for claim event on existing policies
            if agent.active_policies and agent.decide_claim():
                claim_policy_id = random.choice(agent.active_policies)
                pol = marketplace.policies.get(claim_policy_id)
                if pol and pol.status.value == "active":
                    claim_amount = round(random.uniform(pol.coverage * 0.2, pol.coverage * 0.9), 2)
                    claim_req = ClaimRequest(
                        policy_id=claim_policy_id,
                        agent_id=agent.id,
                        reason=agent.pick_claim_reason(),
                        claimed_amount=claim_amount,
                        description=f"Automated claim by {agent.name}",
                    )
                    claim = marketplace.file_claim(claim_req)
                    if claim:
                        agent.total_claims_received += claim.payout
                        if claim_policy_id in agent.active_policies:
                            agent.active_policies.remove(claim_policy_id)
                        result["claim"] = {
                            "reason": claim.reason.value,
                            "payout": claim.payout,
                            "status": claim.status.value,
                        }
            return result
        else:
            return {
                "agent": agent.name,
                "action": "offer_failed",
                "tx_type": tx.tx_type.value,
                "amount": tx.amount,
                "risk": assessment.composite_score,
            }
    else:
        return {
            "agent": agent.name,
            "action": "declined",
            "tx_type": tx.tx_type.value,
            "amount": tx.amount,
            "risk": assessment.composite_score,
            "premium": offer.premium,
        }
