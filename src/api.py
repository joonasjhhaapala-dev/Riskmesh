"""REST API routes for RiskMesh marketplace."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from .marketplace import Marketplace
from .models import (
    ClaimRequest,
    InsureRequest,
    TransactionRequest,
    Transaction,
)

router = APIRouter()

# The marketplace instance is injected via app.state from main.py
_marketplace: Marketplace | None = None


def set_marketplace(mp: Marketplace) -> None:
    global _marketplace
    _marketplace = mp


def get_marketplace() -> Marketplace:
    if _marketplace is None:
        raise RuntimeError("Marketplace not initialized")
    return _marketplace


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/assess")
async def assess_transaction(req: TransactionRequest):
    """Submit a transaction for risk assessment and receive an insurance offer."""
    mp = get_marketplace()
    tx = Transaction(
        agent_id=req.agent_id,
        amount=req.amount,
        tx_type=req.tx_type,
        counterparty=req.counterparty,
        description=req.description,
        context=req.context,
    )
    assessment, offer = mp.submit_transaction(tx)
    return {
        "transaction_id": tx.id,
        "assessment": assessment.model_dump(),
        "offer": offer.model_dump(),
    }


@router.post("/insure")
async def accept_insurance(req: InsureRequest):
    """Accept an insurance offer to create a policy."""
    mp = get_marketplace()
    policy = mp.accept_offer(req)
    if not policy:
        raise HTTPException(status_code=404, detail="Offer not found, expired, or no provider capacity")
    return {"policy": policy.model_dump()}


@router.post("/claim")
async def file_claim(req: ClaimRequest):
    """File a claim against an active policy."""
    mp = get_marketplace()
    claim = mp.file_claim(req)
    if not claim:
        raise HTTPException(status_code=404, detail="Policy not found, not active, or agent mismatch")
    return {"claim": claim.model_dump()}


@router.get("/policies")
async def list_policies(limit: int = Query(50, ge=1, le=500)):
    """List active policies."""
    mp = get_marketplace()
    policies = mp.get_active_policies()
    return {
        "count": len(policies),
        "policies": [p.model_dump() for p in policies[:limit]],
    }


@router.get("/stats")
async def marketplace_stats():
    """Get marketplace statistics."""
    mp = get_marketplace()
    return mp.get_stats().model_dump()


@router.get("/events")
async def recent_events(n: int = Query(40, ge=1, le=200)):
    """Get recent marketplace events."""
    mp = get_marketplace()
    return mp.recent_events(n)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the live dashboard."""
    html_path = Path(__file__).parent / "dashboard.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
