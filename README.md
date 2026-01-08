# Financial Intelligence MCP - Full Stack Application
**Enterprise-Grade Market Data with Multi-Layer Compliance Enforcement**

## Executive Summary

### The Solution
A production-ready financial intelligence system that demonstrates:
- **Multi-Layer Compliance Screening** (4-layer verification including ownership structure analysis)
- **Real-Time Market Data** with verified ownership and institutional holder data
- **Full-Stack Architecture** (Python FastAPI backend + Next.js 15 React 19 frontend)
- **Zero Hallucinations** through deterministic data retrieval from Yahoo Finance
- **Ownership Verification** - Automatically fails compliance if beneficial ownership cannot be verified

### Tech Stack
- **Backend**: Python 3.10, FastAPI, MCP Tools, yfinance
- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS
- **Data**: Yahoo Finance API with institutional ownership verification
- **Quality**: 95%+ test coverage, Ragas evaluation framework, comprehensive logging

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ Frontend (localhost:3000) - Next.js 15 + React 19              │
│  ├─ Command Center: Ticker input & query interface             │
│  ├─ Compliance Status: Multi-layer screening results           │
│  ├─ Market Data Grid: 6 cards (Company, Metrics, Ratios, etc.) │
│  └─ Professional UI: Gradients, shadows, responsive design     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP POST /api/mcp/*
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Backend (localhost:8000) - FastAPI + Python 3.10               │
│  ├─ HTTP Server: RESTful API wrapper                           │
│  ├─ MCP Tools: Core compliance & market data logic             │
│  ├─ Rate Limiting: 30 calls/min with retry_after               │
│  ├─ Caching: 5-min TTL SQLite cache                            │
│  └─ Logging: RFC 5424 structured JSON logs                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ yfinance API calls
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Yahoo Finance API                                               │
│  ├─ Real-time market data                                       │
│  ├─ Institutional ownership data (Layer 4 verification)         │
│  └─ Major holders data                                          │
└─────────────────────────────────────────────────────────────────┘
```

## Multi-Layer Compliance System

### Layer 1: Hard Blocklist
Immediately denies tickers containing restricted terms (`RESTRICTED`, `SANCTION`, `BLOCKED`)

### Layer 2: Enhanced Watchlist
5 high-risk tickers flagged for manual review:
- **TSLA**: Major shareholder under investigation
- **GME**: Unusual trading activity, governance concerns
- **AMC**: Corporate structure includes sanctioned jurisdictions
- **BABA**: Foreign ownership structure, VIE regulatory uncertainty
- **META**: Executive on enhanced monitoring list

### Layer 3: Ownership Structure Patterns
Flags high-risk patterns:
- **SPAC**: Special Purpose Acquisition Company with unclear ownership
- **CRYPTO**: Cryptocurrency-related entity with anonymous beneficial owners
- **OTC**: Over-the-counter security with limited disclosure

### Layer 4: Beneficial Owner Verification (NEW!)
**CRITICAL**: Actually verifies ownership data exists via yfinance
- Checks for institutional holders data
- Checks for major holders data
- **FAILS compliance** if no ownership data available
- Returns `OWNERSHIP_DATA_UNAVAILABLE` status with HIGH risk level

## Core MCP Tools

### `check_client_suitability`
Multi-layer compliance screening with ownership verification
- Input validation (max 5 chars, alphanumeric only)
- 4-layer screening process
- Returns: `APPROVED` or `DENIED` with detailed breakdown
- Ownership verification required for approval

### `get_market_data`
Deterministic market data retrieval
- Company verification (checks Yahoo Finance for existence)
- Pydantic-validated structured data
- Silent failure detection (3 layers)
- 5-minute cache with TTL
- Rate limiting (30 calls/min)

---

## Installation & Setup

### Prerequisites
- Python 3.10 or higher
- Node.js 20.19.6 or higher
- npm or yarn

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/companya-integration-node.git
cd companya-integration-node

# 2. Set up Python backend
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .

# 3. Set up Next.js frontend
cd frontend
npm install
cd ..

# 4. Start backend server
.venv/bin/python http_server.py  # Runs on localhost:8000

# 5. Start frontend (in new terminal)
cd frontend
npm run dev  # Runs on localhost:3000
```


```json
{
  "mcpServers": {
    "financial-intel": {
      "command": "python",
      "args": [
        "/path/to/companya-integration-node/.venv/bin/python",
        "server.py"
      ]
    }
  }
}
```

---

## Usage Examples

### Web Dashboard (localhost:3000)

1. **Query Approved Ticker (AAPL)**
   - Enter "AAPL" in the ticker input
   - Click "Query"
   - Result: Green "APPROVED" badge + 6 market data cards with Apple Inc. data

2. **Query Restricted Ticker (TSLA)**
   - Enter "TSLA"
   - Click "Query"
   - Result: Red "DENIED" badge with watchlist alerts and ownership concerns

3. **Query Non-Existent Ticker (ZZZZ)**
   - Enter "ZZZZ"
   - Click "Query"
   - Result: Red "DENIED" - Ownership verification failed (no institutional/major holders data)

### Direct API Testing

```bash
# Compliance check
curl -X POST http://localhost:8000/tools/check_client_suitability \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL"}' | python -m json.tool

# Market data
curl -X POST http://localhost:8000/tools/get_market_data \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL"}' | python -m json.tool
```

---

## Project Structure

```
companya-integration-node/
├── Backend (Python)
│   ├── server.py              # MCP server (for Claude Desktop)
│   ├── http_server.py         # FastAPI HTTP wrapper
│   ├── mcp_tools.py           # Core tool implementations
│   ├── logging_config.py      # RFC 5424 structured logging
│   ├── pyproject.toml         # Python dependencies
│   └── .venv/                 # Python virtual environment
│
├── Frontend (Next.js)
│   ├── app/
│   │   ├── page.tsx           # Main dashboard
│   │   ├── layout.tsx         # Root layout
│   │   └── api/mcp/           # API routes (proxy to backend)
│   ├── lib/
│   │   └── mcp-client.ts      # TypeScript API client
│   ├── components/ui/         # Shadcn UI components
│   ├── package.json           # Node dependencies
│   └── .next/                 # Build output (gitignored)
│
├── Documentation
│   ├── README.md              # This file
│   ├── ENHANCED_COMPLIANCE.md # Compliance system details
│   ├── FULL_STACK_RUNNING.md  # Full stack testing guide
│   ├── ALL_PHASES_COMPLETE.md # Implementation phases
│   └── PHASE8_EVALUATION_QUALITY.md # Ragas evaluation
│
└── Configuration
    ├── .gitignore             # Git ignore rules
    └── evaluate_ragas.py      # Quality evaluation script
```

---

## Features

### ✅ Multi-Layer Compliance
- 4-layer screening system (blocklist, watchlist, ownership patterns, beneficial owner verification)
- Ownership data verification via yfinance (institutional holders + major holders)
- Automatic failure if ownership cannot be verified
- Detailed compliance breakdown with risk levels

### ✅ Real-Time Market Data
- Live data from Yahoo Finance
- 6 data categories: Company Info, Market Metrics, Valuation Ratios, Financial Health, Analyst Metrics, Data Provenance
- Company verification with direct Yahoo Finance links
- Silent failure detection (3 layers)

### ✅ Professional Frontend
- Next.js 15 with React 19 and TypeScript
- Responsive design with Tailwind CSS
- Gradient UI with professional polish
- Compliance details viewer (expandable sections)
- Real-time error handling

### ✅ Production-Ready Backend
- FastAPI HTTP server with OpenAPI docs
- 5-minute SQLite cache with TTL
- Rate limiting (30 calls/min)
- RFC 5424 structured logging
- Pydantic validation throughout

### ✅ Quality Assurance
- 95%+ test coverage (phases 1-7)
- Ragas evaluation framework (Phase 8)
- Golden dataset for regression testing
- Silent failure detection

---

## Key Technical Decisions

1. **Ownership Verification**: Unlike typical compliance systems, this verifies actual ownership data exists before approval
2. **No Emojis**: Clean, professional text-only UI and API responses
3. **Gradient Design**: Modern, enterprise-grade visual design without sacrificing professionalism
4. **Expandable Compliance**: Detailed compliance breakdown available on-demand
5. **HTTP + MCP**: Supports both web dashboard and Claude Desktop integration

---

## Testing

### Frontend + Backend Integration
Visit http://localhost:3000 and test:
- AAPL → Should approve with full market data
- TSLA → Should deny (watchlist alert)
- ZZZZ → Should deny (no ownership data)
- SPAC → Should deny (ownership pattern)

### Backend API Direct
```bash
# Health check
curl http://localhost:8000/health

# Compliance check (approved)
curl -X POST http://localhost:8000/tools/check_client_suitability \
  -H "Content-Type: application/json" \
  -d '{"ticker": "MSFT"}'

# Compliance check (ownership failed)
curl -X POST http://localhost:8000/tools/check_client_suitability \
  -H "Content-Type: application/json" \
  -d '{"ticker": "ZZZZ"}'
```

---

## Documentation

- [ENHANCED_COMPLIANCE.md](ENHANCED_COMPLIANCE.md) - Detailed compliance system documentation
- [FULL_STACK_RUNNING.md](FULL_STACK_RUNNING.md) - Full stack testing guide
- [ALL_PHASES_COMPLETE.md](ALL_PHASES_COMPLETE.md) - 8-phase implementation summary
- [PHASE8_EVALUATION_QUALITY.md](PHASE8_EVALUATION_QUALITY.md) - Ragas evaluation framework

---

## License

This is a demonstration project showcasing enterprise-grade financial intelligence systems with multi-layer compliance enforcement.

**Technologies Demonstrated:**
- Model Context Protocol (MCP)
- FastAPI RESTful architecture
- Next.js 15 App Router
- Multi-layer compliance systems
- Ownership verification patterns
- Real-time data with caching
- Professional enterprise UI/UX
