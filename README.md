# RiskMesh

[![CI](https://github.com/riskmesh/riskmesh/actions/workflows/ci.yml/badge.svg)](https://github.com/riskmesh/riskmesh/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-green.svg)](https://www.python.org/downloads/)

**Real-time risk pricing and insurance marketplace for AI agent transactions.**

RiskMesh provides automated micro-insurance for every AI agent action. Agents submit transactions, receive Monte Carlo-powered risk assessments and insurance offers in milliseconds, and can accept coverage, file claims, and track their risk portfolio -- all through a REST API with a live dashboard.

---

## Features

- **Monte Carlo Risk Engine** -- 10,000-iteration simulation with Beta distribution sampling across 5 risk dimensions
- **Dynamic Pricing** -- premiums adjust based on expected loss, concentration risk, and operational costs
- **Marketplace Matching** -- automatically pairs transactions with the best underwriting provider based on capacity, risk appetite, and specialization
- **Policy & Claims Management** -- full lifecycle from offer to policy to automated claim adjudication
- **Live Dashboard** -- dark-themed real-time dashboard showing stats, event feed, and active policies
- **Agent Simulation** -- 20 simulated AI agents with diverse risk profiles generating realistic transaction flow
- **REST API** -- FastAPI with auto-generated OpenAPI/Swagger docs

## Architecture

```
                          +------------------+
                          |   AI Agents      |
                          | (20 simulated)   |
                          +--------+---------+
                                   |
                            POST /assess
                                   |
                          +--------v---------+
                          |    FastAPI        |
                          |    REST API       |<---- GET /dashboard
                          +--------+---------+
                                   |
                    +--------------+--------------+
                    |                             |
           +-------v--------+          +---------v-------+
           |  Risk Engine   |          |   Marketplace   |
           |  (Monte Carlo) |          | (Match + Store) |
           +-------+--------+          +---------+-------+
                   |                             |
           Beta distribution             +-------+-------+
           sampling (5 dims)             |               |
           10K iterations           Policies         Claims
                                   & Offers        & Payouts
                                         |
                                +--------v--------+
                                | Risk Providers  |
                                | (4 underwriters)|
                                +-----------------+

src/
  main.py          Entry point, FastAPI app factory, CLI
  api.py           REST API routes
  models.py        Pydantic data models (15 models/enums)
  risk_engine.py   Monte Carlo risk pricing engine
  marketplace.py   Matching engine, policy & claims management
  agents.py        Simulated AI agent behaviors
  simulator.py     Live simulation runner (20 agents)
  dashboard.html   Dark-themed live dashboard (Tailwind CSS)
```

## Quick Start

```bash
# 1. Install
pip install -e ".[dev]"

# 2. Run (API server + live simulation)
python -m src.main

# 3. Open
#    Dashboard:  http://localhost:8001/dashboard
#    API docs:   http://localhost:8001/docs
```

For terminal-only simulation (no API server):

```bash
python -m src.main --sim-only
```

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/assess` | Submit a transaction for risk assessment + insurance offer |
| `POST` | `/insure` | Accept an insurance offer, creating a policy |
| `POST` | `/claim` | File a claim against an active policy |
| `GET` | `/policies` | List active policies |
| `GET` | `/stats` | Marketplace statistics (volumes, ratios, capacity) |
| `GET` | `/events` | Recent activity feed |
| `GET` | `/dashboard` | Live HTML dashboard |
| `GET` | `/docs` | OpenAPI / Swagger UI |

### Example: Assess a Transaction

```bash
curl -X POST http://localhost:8001/assess \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "bot-001",
    "amount": 5000,
    "tx_type": "b2b_purchase",
    "counterparty": "AcmeCorp",
    "description": "Quarterly parts order"
  }'
```

Response includes a full risk assessment (5-dimension scores, composite score, expected loss, confidence) and an insurance offer (premium, coverage, deductible, payout conditions).

## How the Risk Model Works

Each transaction is scored across **5 risk dimensions**:

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| Counterparty | 30% | Default/insolvency risk of the other party |
| Delivery | 20% | Non-delivery or SLA breach probability |
| Price Volatility | 15% | Price movement risk from agreed terms |
| Fraud | 25% | Probability of fraudulent counterparty activity |
| Operational | 10% | System/infrastructure failure risk |

**Scoring** uses Beta distribution sampling. Each dimension has base parameters `(alpha, beta)` tuned per transaction type (e.g., financial transactions have higher price volatility risk). The transaction amount adjusts alpha upward, increasing risk for larger transactions. 500 samples are drawn per dimension for stability.

**Expected Loss** is computed via Monte Carlo simulation (10,000 iterations):

```
For each iteration i:
    P(loss)_i   ~ Beta(composite * 10, (1-composite) * 10)
    severity_i  ~ Beta(composite * 5, (1-composite) * 5)
    loss_i      = P(loss)_i * severity_i * amount

E[loss] = mean(loss_1 ... loss_10000)
```

**Premium** is then calculated as:

```
premium = E[loss] * (1 + risk_margin) * (1 + operational_cost)
```

Where `risk_margin` starts at 35% and increases with counterparty concentration risk, and `operational_cost` is 10%. A minimum premium floor of $0.50 is enforced.

**Coverage ratio** is inversely correlated with composite risk: low-risk transactions get up to 95% coverage, high-risk transactions get as low as 50%.

## Running Tests

```bash
python -m pytest tests/ -v
```

## Transaction Types

| Type | Amount Range | Typical Risk Profile |
|------|-------------|---------------------|
| `shopping` | $50 -- $5K | Low-medium risk |
| `travel` | $200 -- $15K | Medium (price volatility) |
| `b2b_purchase` | $1K -- $50K | Medium (counterparty, delivery) |
| `digital_service` | $100 -- $10K | Low (fraud is main risk) |
| `financial` | $500 -- $100K | High (volatility, counterparty) |
| `logistics` | $300 -- $25K | Medium-high (delivery, operational) |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

[MIT](LICENSE)
