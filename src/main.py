"""RiskMesh — Real-time risk pricing and transfer marketplace for AI agent transactions.

Entry point: starts the FastAPI server on port 8001 with background simulation.

Usage:
    py src/main.py              # API server + background simulation
    py src/main.py --sim-only   # Terminal simulation only (no API)
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router, set_marketplace
from .marketplace import Marketplace
from .simulator import Simulator, run_background_simulation

# ---------------------------------------------------------------------------
# Shared marketplace instance
# ---------------------------------------------------------------------------

marketplace = Marketplace(rng_seed=42)


# ---------------------------------------------------------------------------
# FastAPI lifespan (starts background simulation alongside the server)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background simulation
    task = asyncio.create_task(run_background_simulation(marketplace, delay=1.5))
    print("\n  [RiskMesh] Background simulation started (20 agents)")
    print("  [RiskMesh] Dashboard: http://localhost:8001/dashboard")
    print("  [RiskMesh] API docs:  http://localhost:8001/docs\n")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="RiskMesh",
        description="Real-time risk pricing and transfer marketplace for AI agent transactions",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    set_marketplace(marketplace)
    app.include_router(router)
    return app


app = create_app()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def _run_terminal_sim() -> None:
    """Run terminal-only simulation (no API server)."""
    sim = Simulator(marketplace, num_agents=20)
    await sim.run(rounds=0, delay=0.4)


def main() -> None:
    if "--sim-only" in sys.argv:
        print("[RiskMesh] Starting terminal simulation...")
        asyncio.run(_run_terminal_sim())
    else:
        print("[RiskMesh] Starting API server on port 8001...")
        uvicorn.run(
            "src.main:app",
            host="0.0.0.0",
            port=8001,
            log_level="info",
        )


if __name__ == "__main__":
    main()
