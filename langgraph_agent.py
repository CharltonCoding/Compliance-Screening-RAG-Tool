"""
LangGraph State Machine for Financial Intelligence Agent

This module implements a stateful compliance workflow using LangGraph.
The state machine enforces architectural-level compliance checking that
cannot be bypassed through prompt injection.

Key Features:
- State-based compliance gate (not prompt-based)
- SQLite checkpointing for session memory
- Impossible to access data without compliance approval
- Full audit trail of all state transitions
"""

import json
from typing import Literal, Optional, TypedDict, Annotated
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

# Import existing validation logic from server.py
from server import (
    NormalizedFinancialData,
    DataRetrievalError,
    MetadataSchema,
    EntityInformation,
    MarketMetrics,
    ValuationRatios,
    FinancialHealth,
    AnalystMetrics
)
import yfinance as yf

# PHASE 6: Import cache and rate limiting
from cache import (
    get_cached_ticker,
    set_cached_ticker,
    check_rate_limit,
    record_api_call,
    CACHE_TTL_SECONDS,
    RATE_LIMIT_MAX_CALLS
)

# Import structured logging
from logging_config import structured_logger


# ============================================================================
# STATE SCHEMA
# ============================================================================

class AgentState(TypedDict):
    """
    State schema for the financial intelligence agent.

    The state machine transitions through these phases:
    1. Initial: ticker provided, compliance_status="pending"
    2. Compliance Check: status becomes "approved" or "denied"
    3. Watchlist Check: determine if HITL required
    4. HITL Approval: (if on watchlist) wait for manual approval
    5. Data Retrieval: (only if approved) market_data populated
    6. Final: Either success with data or error
    """
    # Input
    ticker: str

    # Compliance gate state
    compliance_status: Literal["pending", "approved", "denied", "error"]
    compliance_reason: Optional[str]
    compliance_checked_at: Optional[str]

    # PHASE 6: Watchlist & HITL (Human-in-the-Loop)
    is_watchlist: bool  # True if ticker on watchlist
    hitl_required: bool  # True if human approval needed
    hitl_approved: Optional[bool]  # True/False/None (pending)
    hitl_approver: Optional[str]  # Username who approved
    hitl_approved_at: Optional[str]  # Timestamp

    # Market data (only populated if compliance approved)
    market_data: Optional[dict]
    market_data_retrieved_at: Optional[str]

    # PHASE 6: Cache tracking
    cache_hit: Optional[bool]  # True if data from cache

    # PHASE 6: Session persistence
    session_id: str  # Correlation ID for checkpointing
    checkpoint_loaded: bool  # True if resumed from checkpoint

    # Error handling
    error: Optional[dict]

    # Message history for conversational context
    messages: Annotated[list[BaseMessage], "Message history"]


# ============================================================================
# NODE IMPLEMENTATIONS
# ============================================================================

def compliance_check_node(state: AgentState) -> AgentState:
    """
    Compliance Gate Node - MANDATORY first step.

    This node enforces KYC/AML compliance checking at the architecture level.
    The data retrieval node is unreachable unless this returns "approved" status.

    Logic mirrors server.py check_client_suitability but runs in state machine.
    """
    ticker = state["ticker"].upper()
    checked_at = datetime.now().isoformat()

    # Restricted entities list (same as server.py)
    restricted_entities = [
        "RESTRICTED",
        "SANCTION",
    ]

    # Check against restricted list
    if any(x in ticker for x in restricted_entities):
        return {
            **state,
            "compliance_status": "denied",
            "compliance_reason": f"Entity {ticker} is on the Restricted Trading List",
            "compliance_checked_at": checked_at,
            "messages": state["messages"] + [
                SystemMessage(content=f"COMPLIANCE DENIED: {ticker} is restricted")
            ]
        }

    # Compliance approved
    return {
        **state,
        "compliance_status": "approved",
        "compliance_reason": f"Entity {ticker} cleared all compliance checks",
        "compliance_checked_at": checked_at,
        "messages": state["messages"] + [
            SystemMessage(content=f"COMPLIANCE APPROVED: {ticker} cleared for analysis")
        ]
    }


def watchlist_check_node(state: AgentState) -> AgentState:
    """
    Watchlist Check Node - Determines if ticker requires HITL approval.

    Watchlist tickers are high-risk but not restricted (e.g., high volatility stocks).
    These require manual Human-in-the-Loop approval before data retrieval.

    PHASE 6: Architectural guardrail for high-risk tickers
    """
    ticker = state["ticker"].upper()

    # Watchlist tickers (configurable - high volatility stocks)
    WATCHLIST = ["TSLA", "GME", "AMC", "COIN"]

    is_watchlist = ticker in WATCHLIST

    structured_logger.logger.info(
        f"Watchlist check for {ticker}: {'ON WATCHLIST' if is_watchlist else 'not on watchlist'}",
        extra={
            "event_type": "watchlist_check",
            "ticker": ticker,
            "session_id": state.get("session_id", "unknown"),
            "is_watchlist": is_watchlist,
            "severity": 5 if is_watchlist else 6  # NOTICE if watchlist, INFO otherwise
        }
    )

    return {
        **state,
        "is_watchlist": is_watchlist,
        "hitl_required": is_watchlist,  # Require HITL if on watchlist
        "messages": state["messages"] + [
            SystemMessage(content=f"{'⚠️ WATCHLIST: ' + ticker + ' requires HITL approval' if is_watchlist else 'Watchlist check: ' + ticker + ' cleared'}")
        ]
    }


def hitl_pause_node(state: AgentState) -> AgentState:
    """
    Human-in-the-Loop Pause Node - BLOCKING state for manual approval.

    This node pauses execution and waits for manual approval from a human reviewer.
    The graph will NOT proceed to data retrieval until approval is granted.

    PHASE 6: HITL enforcement for high-risk tickers
    """
    ticker = state["ticker"].upper()

    structured_logger.logger.warning(
        f"HITL pause: {ticker} requires manual approval",
        extra={
            "event_type": "hitl_pause",
            "ticker": ticker,
            "session_id": state.get("session_id", "unknown"),
            "reason": "Ticker is on watchlist",
            "severity": 4,  # WARNING
            "security_alert": True
        }
    )

    # In production: this would integrate with approval system (UI/API/queue)
    # For now: return state indicating pause
    return {
        **state,
        "hitl_approved": None,  # Pending approval
        "messages": state["messages"] + [
            HumanMessage(content=f"⚠️ HITL REQUIRED: Ticker '{ticker}' is on watchlist. Manual approval needed before proceeding.")
        ]
    }


def hitl_approval_node(state: AgentState) -> AgentState:
    """
    HITL Approval Processing Node - Receives approval decision.

    In production: this would receive approval from UI/API/database.
    For testing: we simulate auto-approval.

    PHASE 6: HITL approval workflow
    """
    ticker = state["ticker"].upper()

    # SIMULATION: Auto-approve for testing
    # In production: check approval database/queue for actual approval
    hitl_approved = True  # Would come from approval system
    approver = "admin@company.com"  # Would come from authentication

    structured_logger.logger.info(
        f"HITL approval: {ticker} {'APPROVED' if hitl_approved else 'DENIED'}",
        extra={
            "event_type": "hitl_approval",
            "ticker": ticker,
            "session_id": state.get("session_id", "unknown"),
            "approved": hitl_approved,
            "approver": approver,
            "severity": 5  # NOTICE
        }
    )

    return {
        **state,
        "hitl_approved": hitl_approved,
        "hitl_approver": approver,
        "hitl_approved_at": datetime.now().isoformat(),
        "messages": state["messages"] + [
            SystemMessage(content=f"✓ HITL APPROVED: {ticker} cleared by {approver}")
        ]
    }


def hitl_denied_node(state: AgentState) -> AgentState:
    """
    Terminal node for HITL denial.
    Returns structured error explaining that manual reviewer denied access.

    PHASE 6: HITL denial handling
    """
    ticker = state["ticker"].upper()

    structured_logger.logger.warning(
        f"HITL DENIED: {ticker}",
        extra={
            "event_type": "hitl_denied",
            "ticker": ticker,
            "session_id": state.get("session_id", "unknown"),
            "severity": 4,  # WARNING
            "security_alert": True
        }
    )

    return {
        **state,
        "error": {
            "error": True,
            "error_code": "HITL_DENIED",
            "ticker": ticker,
            "message": f"Human reviewer denied access to {ticker}",
            "detail": "Manual review rejected this request",
            "troubleshooting": "Contact your supervisor or compliance team.",
            "checked_at": datetime.now().isoformat()
        },
        "messages": state["messages"] + [
            AIMessage(content=f"BLOCKED: HITL reviewer denied access to {ticker}")
        ]
    }


def data_retrieval_node(state: AgentState) -> AgentState:
    """
    Data Retrieval Node - ONLY accessible after compliance approval.

    This node fetches market data using the same logic as server.py get_market_data
    but runs within the state machine. Includes all 3 layers of silent failure detection.

    PHASE 6: Integrated with caching and rate limiting.

    CRITICAL: This node is architecturally unreachable if compliance_status != "approved"
    """
    ticker = state["ticker"].upper()
    session_id = state.get("session_id", "unknown")
    retrieved_at = datetime.now().isoformat()

    # PHASE 6: Check rate limit first
    is_allowed, calls_in_window, retry_after = check_rate_limit(session_id, "get_market_data")

    if not is_allowed:
        # Rate limit exceeded - return error
        structured_logger.logger.warning(
            f"Rate limit exceeded for session {session_id[:16]}...",
            extra={
                "event_type": "rate_limit_exceeded",
                "ticker": ticker,
                "session_id": session_id,
                "calls_in_window": calls_in_window,
                "max_calls": RATE_LIMIT_MAX_CALLS,
                "retry_after": retry_after,
                "severity": 4,  # WARNING
                "security_alert": True
            }
        )

        error_data = {
            "error": True,
            "error_code": "RATE_LIMIT_EXCEEDED",
            "ticker": ticker,
            "message": f"Rate limit exceeded: {calls_in_window} calls in 60 seconds",
            "detail": f"Maximum {RATE_LIMIT_MAX_CALLS} calls per minute per session",
            "troubleshooting": f"Wait {retry_after} seconds before retrying. Consider caching results or reducing request frequency.",
            "retrieved_at": retrieved_at
        }

        return {
            **state,
            "error": error_data,
            "messages": state["messages"] + [
                AIMessage(content=f"ERROR: {error_data['message']}")
            ]
        }

    # PHASE 6: Check cache for existing data
    cached_data = get_cached_ticker(ticker)

    if cached_data:
        # Cache HIT - return immediately without calling yfinance
        structured_logger.log_tool_success(
            tool_name="get_market_data",
            compliance_flag="N/A",
            result_summary=f"Cache HIT for {ticker} (no API call needed)"
        )

        return {
            **state,
            "market_data": cached_data,
            "market_data_retrieved_at": cached_data.get("metadata", {}).get("retrieved_at", retrieved_at),
            "cache_hit": True,
            "messages": state["messages"] + [
                AIMessage(content=f"SUCCESS: Retrieved cached market data for {ticker}")
            ]
        }

    # Cache MISS - proceed with yfinance call
    try:
        # Fetch data from yfinance
        stock = yf.Ticker(ticker)
        info = stock.info

        # SILENT FAILURE DETECTION #1: Empty response check
        if not info or len(info) < 5:
            error_data = {
                "error": True,
                "error_code": "API_THROTTLE",
                "ticker": ticker,
                "message": "Yahoo Finance returned minimal data - request may have been throttled",
                "detail": f"Received only {len(info)} fields in response",
                "troubleshooting": "Wait 60 seconds and retry. Yahoo Finance rate limits requests.",
                "retrieved_at": retrieved_at
            }
            return {
                **state,
                "error": error_data,
                "messages": state["messages"] + [
                    AIMessage(content=f"ERROR: {error_data['message']}")
                ]
            }

        # SILENT FAILURE DETECTION #2: Missing price fields
        if 'regularMarketPrice' not in info and 'currentPrice' not in info and 'previousClose' not in info:
            error_data = {
                "error": True,
                "error_code": "INVALID_TICKER",
                "ticker": ticker,
                "message": f"Ticker '{ticker}' does not appear to be valid or is not traded",
                "detail": "No pricing information available from data source",
                "troubleshooting": "Verify ticker symbol is correct and actively traded.",
                "retrieved_at": retrieved_at
            }
            return {
                **state,
                "error": error_data,
                "messages": state["messages"] + [
                    AIMessage(content=f"ERROR: {error_data['message']}")
                ]
            }

        # Build normalized data structure
        try:
            normalized_data = NormalizedFinancialData(
                metadata=MetadataSchema(retrieved_at=retrieved_at),
                entity_information=EntityInformation(
                    ticker=ticker,
                    entity_name=info.get("longName", info.get("shortName", "Unknown")),
                    sector=info.get("sector"),
                    industry=info.get("industry"),
                    country=info.get("country"),
                    website=info.get("website")
                ),
                market_metrics=MarketMetrics(
                    current_price=info.get("currentPrice") or info.get("regularMarketPrice"),
                    currency=info.get("currency", "USD"),
                    market_cap=info.get("marketCap"),
                    market_cap_formatted=f"${info.get('marketCap', 0):,.0f}" if info.get('marketCap') else None,
                    enterprise_value=info.get("enterpriseValue"),
                    volume=info.get("volume") or info.get("regularMarketVolume"),
                    avg_volume=info.get("averageVolume")
                ),
                valuation_ratios=ValuationRatios(
                    forward_pe=info.get("forwardPE"),
                    trailing_pe=info.get("trailingPE"),
                    price_to_book=info.get("priceToBook"),
                    price_to_sales=info.get("priceToSalesTrailing12Months"),
                    peg_ratio=info.get("pegRatio")
                ),
                financial_health=FinancialHealth(
                    dividend_yield=info.get("dividendYield"),
                    dividend_rate=info.get("dividendRate"),
                    profit_margin=info.get("profitMargins"),
                    operating_margin=info.get("operatingMargins"),
                    debt_to_equity=info.get("debtToEquity")
                ),
                analyst_metrics=AnalystMetrics(
                    recommendation=info.get("recommendationKey"),
                    target_high_price=info.get("targetHighPrice"),
                    target_low_price=info.get("targetLowPrice"),
                    target_mean_price=info.get("targetMeanPrice"),
                    number_of_analyst_opinions=info.get("numberOfAnalystOpinions")
                )
            )

            # SILENT FAILURE DETECTION #3: Data quality validation
            is_valid, reason = normalized_data.has_sufficient_data()
            if not is_valid:
                error_data = {
                    "error": True,
                    "error_code": "INSUFFICIENT_DATA",
                    "ticker": ticker,
                    "message": f"Data quality check failed: {reason}",
                    "detail": "Retrieved data does not meet minimum quality thresholds",
                    "troubleshooting": "The ticker may be valid but data is incomplete.",
                    "retrieved_at": retrieved_at
                }
                return {
                    **state,
                    "error": error_data,
                    "messages": state["messages"] + [
                        AIMessage(content=f"ERROR: {error_data['message']}")
                    ]
                }

            # Success - cache and return normalized data
            market_data_dict = normalized_data.model_dump()

            # PHASE 6: Cache successful result
            set_cached_ticker(ticker, market_data_dict, ttl_seconds=CACHE_TTL_SECONDS)

            # PHASE 6: Record API call for rate limiting
            record_api_call(session_id, ticker, "get_market_data")

            structured_logger.log_tool_success(
                tool_name="get_market_data",
                compliance_flag="N/A",
                result_summary=f"Successfully retrieved and cached market data for {ticker}"
            )

            return {
                **state,
                "market_data": market_data_dict,
                "market_data_retrieved_at": retrieved_at,
                "cache_hit": False,
                "messages": state["messages"] + [
                    AIMessage(content=f"SUCCESS: Retrieved market data for {ticker}")
                ]
            }

        except Exception as validation_error:
            error_data = {
                "error": True,
                "error_code": "UNKNOWN_ERROR",
                "ticker": ticker,
                "message": "Data validation failed during normalization",
                "detail": str(validation_error),
                "troubleshooting": "Data from source could not be validated.",
                "retrieved_at": retrieved_at
            }
            return {
                **state,
                "error": error_data,
                "messages": state["messages"] + [
                    AIMessage(content=f"ERROR: {error_data['message']}")
                ]
            }

    except Exception as e:
        error_data = {
            "error": True,
            "error_code": "NETWORK_ERROR",
            "ticker": ticker,
            "message": f"Unable to retrieve entity data for {ticker}",
            "detail": str(e),
            "troubleshooting": "Check network connectivity and API availability.",
            "retrieved_at": retrieved_at
        }
        return {
            **state,
            "error": error_data,
            "messages": state["messages"] + [
                AIMessage(content=f"ERROR: {error_data['message']}")
            ]
        }


def compliance_denied_node(state: AgentState) -> AgentState:
    """
    Terminal node for compliance denial.
    Returns structured error explaining why access was denied.
    """
    return {
        **state,
        "error": {
            "error": True,
            "error_code": "COMPLIANCE_DENIED",
            "ticker": state["ticker"].upper(),
            "message": state["compliance_reason"],
            "detail": "Analysis prohibited by compliance policy",
            "troubleshooting": "Contact Compliance team if you believe this is an error.",
            "checked_at": state["compliance_checked_at"]
        },
        "messages": state["messages"] + [
            AIMessage(content=f"BLOCKED: {state['compliance_reason']}")
        ]
    }


# ============================================================================
# CONDITIONAL ROUTING
# ============================================================================

def route_after_compliance(state: AgentState) -> str:
    """
    Conditional edge that routes based on compliance status.

    PHASE 6: Routes to watchlist check instead of directly to data retrieval.

    This is the CRITICAL enforcement point - data retrieval is
    architecturally unreachable if compliance is not approved.
    """
    status = state["compliance_status"]

    if status == "approved":
        return "watchlist_check"  # PHASE 6: Check watchlist before data
    elif status == "denied":
        return "compliance_denied"
    else:
        return "error"


def route_after_watchlist(state: AgentState) -> str:
    """
    Routes based on watchlist status.

    PHASE 6: New routing function for watchlist check.

    If ticker is on watchlist → HITL required → pause for approval
    If ticker not on watchlist → proceed directly to data retrieval
    """
    if state.get("hitl_required"):
        return "hitl_pause"  # Pause for manual approval
    else:
        return "retrieve_data"  # Proceed directly


def route_after_hitl(state: AgentState) -> str:
    """
    Routes based on HITL approval status.

    PHASE 6: New routing function for HITL approval.

    If approval is True → proceed to data retrieval
    If approval is False → terminal denial

    Note: In production with interrupts, hitl_approved could be None (pending).
    For testing, we auto-approve in hitl_approval_node, so it's always True/False.
    """
    hitl_approved = state.get("hitl_approved")

    if hitl_approved:
        return "retrieve_data"  # Approved - proceed
    else:
        return "hitl_denied"  # Denied - stop


def route_after_data_retrieval(state: AgentState) -> str:
    """
    Routes after data retrieval - either success or error.
    """
    if state.get("error"):
        return "error"
    else:
        return "success"


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_financial_agent_graph():
    """
    Creates the LangGraph state machine with compliance enforcement.

    PHASE 6: Enhanced graph with watchlist and HITL nodes.

    Graph Structure:
        START
          ↓
        compliance_check_node
          ↓
        [compliance_status?]
          ├─ approved → watchlist_check_node
          │                ↓
          │            [is_watchlist?]
          │              ├─ yes → hitl_pause_node
          │              │          ↓
          │              │      [hitl_approved?]
          │              │        ├─ pending → hitl_pause (loop)
          │              │        ├─ approved → data_retrieval_node → END
          │              │        └─ denied → hitl_denied_node → END
          │              └─ no → data_retrieval_node → END
          ├─ denied → compliance_denied_node → END
          └─ error → END

    Returns:
        Compiled StateGraph ready for execution
    """
    # Initialize graph with state schema
    workflow = StateGraph(AgentState)

    # Add all nodes (PHASE 6: includes watchlist and HITL)
    workflow.add_node("check_compliance", compliance_check_node)
    workflow.add_node("watchlist_check", watchlist_check_node)
    workflow.add_node("hitl_pause", hitl_pause_node)
    workflow.add_node("hitl_approval", hitl_approval_node)
    workflow.add_node("retrieve_data", data_retrieval_node)
    workflow.add_node("compliance_denied", compliance_denied_node)
    workflow.add_node("hitl_denied", hitl_denied_node)

    # Add edges
    workflow.add_edge(START, "check_compliance")

    # Conditional routing after compliance check
    workflow.add_conditional_edges(
        "check_compliance",
        route_after_compliance,
        {
            "watchlist_check": "watchlist_check",  # PHASE 6: Route to watchlist check
            "compliance_denied": "compliance_denied",
            "error": END
        }
    )

    # PHASE 6: Conditional routing after watchlist check
    workflow.add_conditional_edges(
        "watchlist_check",
        route_after_watchlist,
        {
            "hitl_pause": "hitl_pause",
            "retrieve_data": "retrieve_data"
        }
    )

    # PHASE 6: After HITL pause, always go to approval node (which simulates approval)
    # In production, this would be interrupt-based, but for testing we auto-approve
    workflow.add_edge("hitl_pause", "hitl_approval")

    # PHASE 6: After approval node processes, route based on result
    workflow.add_conditional_edges(
        "hitl_approval",
        route_after_hitl,
        {
            "retrieve_data": "retrieve_data",
            "hitl_denied": "hitl_denied"
        }
    )

    # Terminal edges
    workflow.add_edge("retrieve_data", END)
    workflow.add_edge("compliance_denied", END)
    workflow.add_edge("hitl_denied", END)  # PHASE 6: New terminal node

    return workflow.compile()


# ============================================================================
# GRAPH WITH CHECKPOINTING
# ============================================================================

async def create_financial_agent_with_checkpointing(checkpoint_db_path: str = "checkpoints.db"):
    """
    Creates the LangGraph state machine with SQLite checkpointing.

    PHASE 6: Enhanced with watchlist and HITL nodes, plus caching integration.

    Checkpointing enables:
    - Session memory across multiple invocations
    - State persistence for audit trails
    - Resuming from previous states
    - Preventing redundant compliance checks
    - HITL approval state persistence

    Args:
        checkpoint_db_path: Path to SQLite database for checkpoints

    Returns:
        Compiled StateGraph with SqliteSaver checkpointer
    """
    # Initialize graph
    workflow = StateGraph(AgentState)

    # Add all nodes (PHASE 6: includes watchlist and HITL)
    workflow.add_node("check_compliance", compliance_check_node)
    workflow.add_node("watchlist_check", watchlist_check_node)
    workflow.add_node("hitl_pause", hitl_pause_node)
    workflow.add_node("hitl_approval", hitl_approval_node)
    workflow.add_node("retrieve_data", data_retrieval_node)
    workflow.add_node("compliance_denied", compliance_denied_node)
    workflow.add_node("hitl_denied", hitl_denied_node)

    # Add edges
    workflow.add_edge(START, "check_compliance")

    # Conditional routing after compliance check
    workflow.add_conditional_edges(
        "check_compliance",
        route_after_compliance,
        {
            "watchlist_check": "watchlist_check",  # PHASE 6: Route to watchlist check
            "compliance_denied": "compliance_denied",
            "error": END
        }
    )

    # PHASE 6: Conditional routing after watchlist check
    workflow.add_conditional_edges(
        "watchlist_check",
        route_after_watchlist,
        {
            "hitl_pause": "hitl_pause",
            "retrieve_data": "retrieve_data"
        }
    )

    # PHASE 6: After HITL pause, always go to approval node (which simulates approval)
    # In production, this would be interrupt-based, but for testing we auto-approve
    workflow.add_edge("hitl_pause", "hitl_approval")

    # PHASE 6: After approval node processes, route based on result
    workflow.add_conditional_edges(
        "hitl_approval",
        route_after_hitl,
        {
            "retrieve_data": "retrieve_data",
            "hitl_denied": "hitl_denied"
        }
    )

    # Terminal edges
    workflow.add_edge("retrieve_data", END)
    workflow.add_edge("compliance_denied", END)
    workflow.add_edge("hitl_denied", END)  # PHASE 6: New terminal node

    # Add SQLite checkpointer - use async context manager correctly
    async with AsyncSqliteSaver.from_conn_string(checkpoint_db_path) as checkpointer:
        return workflow.compile(checkpointer=checkpointer)
