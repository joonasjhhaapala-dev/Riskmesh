"""Live simulation of 20 AI agents transacting in the RiskMesh marketplace."""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone

from .agents import create_agents, run_agent_cycle
from .marketplace import Marketplace
from .models import RiskProvider, TransactionType


# ---------------------------------------------------------------------------
# Default risk providers
# ---------------------------------------------------------------------------

DEFAULT_PROVIDERS = [
    RiskProvider(
        name="AlphaShield Underwriters",
        capacity=500_000,
        risk_appetite=0.7,
        min_premium_rate=0.008,
        specialties=[TransactionType.FINANCIAL, TransactionType.B2B_PURCHASE],
    ),
    RiskProvider(
        name="NovaCover Re",
        capacity=1_000_000,
        risk_appetite=0.6,
        min_premium_rate=0.01,
        specialties=[TransactionType.SHOPPING, TransactionType.DIGITAL_SERVICE],
    ),
    RiskProvider(
        name="GlobalRisk Partners",
        capacity=750_000,
        risk_appetite=0.8,
        min_premium_rate=0.005,
        specialties=[TransactionType.LOGISTICS, TransactionType.TRAVEL],
    ),
    RiskProvider(
        name="MicroInsure DAO",
        capacity=300_000,
        risk_appetite=0.9,
        min_premium_rate=0.003,
        specialties=[],
    ),
]


# ---------------------------------------------------------------------------
# Terminal display helpers
# ---------------------------------------------------------------------------

COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "cyan": "\033[36m",
    "magenta": "\033[35m",
    "blue": "\033[34m",
    "white": "\033[97m",
    "bg_dark": "\033[40m",
}


def _c(text: str, *styles: str) -> str:
    codes = "".join(COLORS.get(s, "") for s in styles)
    return f"{codes}{text}{COLORS['reset']}"


def print_header() -> None:
    print("\n" + "=" * 72)
    print(_c("  RISKMESH  ", "bold", "cyan") + _c("  Real-Time Risk Pricing Marketplace", "white"))
    print(_c("  Simulating 20 AI agents with live risk pricing", "dim"))
    print("=" * 72 + "\n")


def print_event(event: dict) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    agent = event["agent"]
    action = event["action"]
    tx_type = event["tx_type"]
    amount = event["amount"]

    if action == "insured":
        risk = event["risk"]
        premium = event["premium"]
        coverage = event["coverage"]
        risk_color = "green" if risk < 0.3 else ("yellow" if risk < 0.6 else "red")
        line = (
            f"  {_c(ts, 'dim')} "
            f"{_c('INSURED', 'bold', 'green')}  "
            f"{_c(agent, 'cyan'):30s} "
            f"{tx_type:18s} "
            f"${amount:>10,.2f}  "
            f"risk={_c(f'{risk:.2f}', risk_color)}  "
            f"premium={_c(f'${premium:.2f}', 'yellow')}  "
            f"coverage={_c(f'${coverage:,.2f}', 'green')}"
        )
        print(line)

        if "claim" in event:
            cl = event["claim"]
            claim_color = "green" if cl["status"] == "approved" else "red"
            payout_val = cl["payout"]
            reason_val = cl["reason"]
            status_val = cl["status"]
            print(
                f"  {' ' * 8} "
                f"{_c('CLAIM', 'bold', 'red')}    "
                f"reason={reason_val:24s} "
                f"payout={_c(f'${payout_val:,.2f}', claim_color)}  "
                f"[{_c(status_val, claim_color)}]"
            )

    elif action == "declined":
        risk = event["risk"]
        premium = event["premium"]
        print(
            f"  {_c(ts, 'dim')} "
            f"{_c('DECLINED', 'bold', 'dim')}  "
            f"{_c(agent, 'dim'):30s} "
            f"{tx_type:18s} "
            f"${amount:>10,.2f}  "
            f"risk={risk:.2f}  "
            f"premium=${premium:.2f}"
        )

    elif action == "offer_failed":
        print(
            f"  {_c(ts, 'dim')} "
            f"{_c('NO MATCH', 'bold', 'magenta')}  "
            f"{_c(agent, 'dim'):30s} "
            f"{tx_type:18s} "
            f"${amount:>10,.2f}"
        )


def print_stats(marketplace: Marketplace) -> None:
    s = marketplace.get_stats()
    print("\n" + "-" * 72)
    print(_c("  MARKETPLACE STATS", "bold", "white"))
    print(f"  Transactions: {_c(str(s.total_transactions), 'cyan'):>6s}   "
          f"Policies: {_c(str(s.total_policies), 'green'):>6s}   "
          f"Claims: {_c(str(s.total_claims), 'red'):>6s}   "
          f"Claims ratio: {_c(f'{s.claims_ratio:.1%}', 'yellow')}")
    print(f"  Premiums: {_c(f'${s.total_premium_volume:,.2f}', 'green'):>14s}   "
          f"Coverage: {_c(f'${s.total_coverage_volume:,.2f}', 'cyan'):>14s}   "
          f"Payouts: {_c(f'${s.total_payouts:,.2f}', 'red'):>14s}")
    print(f"  Avg risk: {_c(f'{s.avg_composite_risk:.3f}', 'yellow'):>8s}   "
          f"Providers: {s.active_providers}   "
          f"Capacity used: {_c(f'${s.used_provider_capacity:,.0f}', 'magenta')}"
          f" / ${s.total_provider_capacity:,.0f}")
    print("-" * 72)


# ---------------------------------------------------------------------------
# Simulation loop
# ---------------------------------------------------------------------------

class Simulator:
    """Runs the marketplace simulation."""

    def __init__(self, marketplace: Marketplace, num_agents: int = 20) -> None:
        self.marketplace = marketplace
        self.agents = create_agents(num_agents)
        self._running = False

        # Register default providers
        for prov in DEFAULT_PROVIDERS:
            marketplace.register_provider(prov)

    async def run(self, rounds: int = 0, delay: float = 0.4) -> None:
        """Run simulation. If rounds=0, run indefinitely."""
        self._running = True
        print_header()

        print(_c("  Providers:", "bold"))
        for p in self.marketplace.providers.values():
            print(f"    - {_c(p.name, 'cyan')}  capacity=${p.capacity:,.0f}  "
                  f"appetite={p.risk_appetite:.1f}  "
                  f"specialties={[s.value for s in p.specialties]}")
        print()

        print(_c("  Agents:", "bold"))
        for a in self.agents[:5]:
            print(f"    - {_c(a.name, 'cyan')}  tolerance={a.risk_tolerance:.2f}  "
                  f"prefs={[t.value for t in a.preferred_types]}")
        print(f"    ... and {len(self.agents) - 5} more\n")

        print(_c("  Starting live simulation...\n", "bold", "green"))

        round_num = 0
        try:
            while self._running:
                round_num += 1
                if rounds > 0 and round_num > rounds:
                    break

                # Pick a random subset of agents to act this round
                active = random.sample(self.agents, k=min(random.randint(1, 5), len(self.agents)))

                for agent in active:
                    event = run_agent_cycle(agent, self.marketplace)
                    if event:
                        print_event(event)

                # Print stats every 10 rounds
                if round_num % 10 == 0:
                    print_stats(self.marketplace)

                await asyncio.sleep(delay)

        except KeyboardInterrupt:
            pass

        print_stats(self.marketplace)
        print(_c("\n  Simulation ended.\n", "bold"))

    def stop(self) -> None:
        self._running = False


async def run_background_simulation(marketplace: Marketplace, delay: float = 1.5) -> None:
    """Background simulation loop for use alongside the API server."""
    sim = Simulator(marketplace, num_agents=20)
    # Run silently in background — no terminal output
    # Note: Simulator.__init__ already registers DEFAULT_PROVIDERS
    sim._running = True

    agents = sim.agents
    while sim._running:
        active = random.sample(agents, k=min(random.randint(1, 3), len(agents)))
        for agent in active:
            run_agent_cycle(agent, marketplace)
        await asyncio.sleep(delay)
