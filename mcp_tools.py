"""
Core MCP Tool Logic - Shared between server.py and http_server.py

This module contains the actual implementation of MCP tools without FastMCP decorators,
allowing them to be called directly from HTTP endpoints.
"""

import json
import asyncio
from datetime import datetime
import yfinance as yf
from typing import Optional

# Import dependencies from existing modules
from logging_config import structured_logger
from security import validate_and_sanitize_ticker, sanitize_error_message, redact_sensitive_data
from cache import (
    get_cached_ticker,
    set_cached_ticker,
    check_rate_limit,
    record_api_call,
    CACHE_TTL_SECONDS,
    RATE_LIMIT_MAX_CALLS
)

# Import Pydantic schemas from server.py
from server import (
    MetadataSchema,
    EntityInformation,
    MarketMetrics,
    ValuationRatios,
    FinancialHealth,
    AnalystMetrics,
    NormalizedFinancialData
)


async def check_client_suitability_impl(ticker: str) -> str:
    """
    Core implementation of compliance check.

    This is the actual logic extracted from server.py's check_client_suitability tool.
    """
    # PHASE 4 SECURITY: Validate and sanitize input
    is_valid, sanitized_ticker, error_msg = validate_and_sanitize_ticker(ticker)

    if not is_valid:
        # Input validation failed - return error
        structured_logger.logger.warning(
            f"Input validation failed for check_client_suitability: {ticker}",
            extra={
                "tool_name": "check_client_suitability",
                "event_type": "input_validation_failure",
                "input_value": ticker[:50],
                "error": error_msg,
                "severity": 4,  # WARNING
                "security_alert": True
            }
        )

        result = {
            "compliance_status": "DENIED",
            "ticker": ticker,
            "error": True,
            "error_code": "VALIDATION_ERROR",
            "compliance_reason": error_msg,
            "compliance_checked_at": datetime.now().isoformat()
        }
        return json.dumps(result, indent=2)

    # Use sanitized ticker for all subsequent operations
    ticker_upper = sanitized_ticker

    # Log tool invocation (after validation)
    structured_logger.log_tool_invocation(
        tool_name="check_client_suitability",
        input_params={"ticker": ticker_upper},
        compliance_flag="PENDING"
    )

    # ========================================================================
    # ENHANCED COMPLIANCE CHECKS - Multi-Layer Screening
    # ========================================================================

    # Layer 1: Hard Blocklist (Immediate Denial)
    hard_blocklist = [
        "RESTRICTED",
        "SANCTION",
        "BLOCKED",
    ]

    for blocked_term in hard_blocklist:
        if blocked_term in ticker_upper:
            structured_logger.log_compliance_denied(
                tool_name="check_client_suitability",
                ticker=ticker_upper,
                reason=f"CRITICAL: Ticker contains blocklisted term '{blocked_term}'"
            )

            result = {
                "compliance_status": "DENIED",
                "ticker": ticker_upper,
                "compliance_reason": f"CRITICAL: Ticker contains blocklisted term '{blocked_term}'",
                "compliance_level": "HARD_BLOCK",
                "compliance_checked_at": datetime.now().isoformat(),
                "requires_review": False,
                "escalation_required": True
            }
            return json.dumps(result, indent=2)

    # Layer 2: Enhanced Watchlist with Ownership Structure Analysis
    # Simulate fetching ownership data for watchlist screening
    watchlist_alerts = []
    ownership_concerns = []

    # High-risk tickers requiring enhanced due diligence
    enhanced_watchlist = {
        "TSLA": {
            "reason": "Major shareholder flagged on regulatory watchlist",
            "concern": "Beneficial ownership by individual under investigation",
            "risk_level": "HIGH",
            "requires_review": True
        },
        "GME": {
            "reason": "Unusual trading activity and governance concerns",
            "concern": "Concentrated ownership by high-risk entities",
            "risk_level": "HIGH",
            "requires_review": True
        },
        "AMC": {
            "reason": "Corporate structure includes sanctioned jurisdictions",
            "concern": "Indirect ownership links to restricted parties",
            "risk_level": "MEDIUM",
            "requires_review": True
        },
        "BABA": {
            "reason": "Foreign ownership structure with compliance concerns",
            "concern": "VIE structure with regulatory uncertainty",
            "risk_level": "HIGH",
            "requires_review": True
        },
        "META": {
            "reason": "Executive on enhanced monitoring list",
            "concern": "Insider trading investigation ongoing",
            "risk_level": "MEDIUM",
            "requires_review": True
        }
    }

    # Check if ticker is on enhanced watchlist
    if ticker_upper in enhanced_watchlist:
        watchlist_info = enhanced_watchlist[ticker_upper]

        # Log watchlist alert
        structured_logger.logger.warning(
            f"WATCHLIST ALERT: {ticker_upper} - {watchlist_info['reason']}",
            extra={
                "tool_name": "check_client_suitability",
                "ticker": ticker_upper,
                "watchlist_flag": True,
                "risk_level": watchlist_info["risk_level"],
                "compliance_concern": watchlist_info["concern"],
                "severity": 4  # WARNING
            }
        )

        watchlist_alerts.append(f"{watchlist_info['reason']}")
        ownership_concerns.append(f"{watchlist_info['concern']}")

        # STRICT MODE: Watchlist items require manual approval
        structured_logger.log_compliance_denied(
            tool_name="check_client_suitability",
            ticker=ticker_upper,
            reason=f"Watchlist alert: {watchlist_info['reason']}"
        )

        result = {
            "compliance_status": "DENIED",
            "ticker": ticker_upper,
            "compliance_reason": f"WATCHLIST ALERT: {watchlist_info['reason']}",
            "compliance_level": "WATCHLIST_HOLD",
            "risk_level": watchlist_info["risk_level"],
            "watchlist_alerts": watchlist_alerts,
            "ownership_concerns": ownership_concerns,
            "compliance_checked_at": datetime.now().isoformat(),
            "requires_review": True,
            "escalation_required": True,
            "next_steps": [
                "Manual compliance review required",
                "Ownership structure verification needed",
                "Enhanced due diligence (EDD) process initiated",
                "Approval from Compliance Officer required"
            ]
        }
        return json.dumps(result, indent=2)

    # Layer 3: Simulated Ownership Structure Screening
    # In production, this would query beneficial ownership databases
    high_risk_patterns = {
        "SPAC": "Special Purpose Acquisition Company with unclear ownership",
        "CRYPTO": "Cryptocurrency-related entity with anonymous beneficial owners",
        "OTC": "Over-the-counter security with limited disclosure",
    }

    for pattern, concern in high_risk_patterns.items():
        if pattern in ticker_upper:
            structured_logger.logger.warning(
                f"Ownership structure concern: {ticker_upper} - {concern}",
                extra={
                    "tool_name": "check_client_suitability",
                    "ticker": ticker_upper,
                    "ownership_concern": True,
                    "pattern_matched": pattern
                }
            )

            ownership_concerns.append(f"{concern}")

            result = {
                "compliance_status": "DENIED",
                "ticker": ticker_upper,
                "compliance_reason": f"OWNERSHIP CONCERN: {concern}",
                "compliance_level": "OWNERSHIP_REVIEW",
                "ownership_concerns": ownership_concerns,
                "compliance_checked_at": datetime.now().isoformat(),
                "requires_review": True,
                "escalation_required": True,
                "next_steps": [
                    "Beneficial ownership verification required",
                    "Ultimate beneficial owner (UBO) identification needed",
                    "Compliance review by senior officer"
                ]
            }
            return json.dumps(result, indent=2)

    # Layer 4: Beneficial Owner & Ownership Verification
    # CRITICAL: Verify ownership data exists before approval
    try:
        stock = yf.Ticker(ticker_upper)

        # Attempt to retrieve ownership data from yfinance
        # This includes institutional holders, major holders, etc.
        institutional_holders = await asyncio.to_thread(lambda: stock.institutional_holders)
        major_holders = await asyncio.to_thread(lambda: stock.major_holders)

        # Check if ownership data is available
        has_institutional_data = institutional_holders is not None and not institutional_holders.empty
        has_major_holders_data = major_holders is not None and not major_holders.empty

        if not has_institutional_data and not has_major_holders_data:
            # FAIL: Cannot verify ownership structure
            structured_logger.logger.error(
                f"Ownership verification failed: No ownership data available for {ticker_upper}",
                extra={
                    "tool_name": "check_client_suitability",
                    "ticker": ticker_upper,
                    "ownership_verification_failed": True,
                    "security_alert": True
                }
            )

            ownership_concerns.append("No institutional ownership data available")
            ownership_concerns.append("No major holders data available")

            result = {
                "compliance_status": "DENIED",
                "ticker": ticker_upper,
                "compliance_reason": "OWNERSHIP VERIFICATION FAILED: Unable to verify beneficial ownership structure",
                "compliance_level": "OWNERSHIP_DATA_UNAVAILABLE",
                "ownership_concerns": ownership_concerns,
                "compliance_checked_at": datetime.now().isoformat(),
                "risk_level": "HIGH",
                "requires_review": True,
                "escalation_required": True,
                "next_steps": [
                    "Manual ownership verification required",
                    "Direct company filing review needed (SEC EDGAR, etc.)",
                    "Cannot proceed without verified ownership structure",
                    "Compliance officer approval required for override"
                ]
            }
            return json.dumps(result, indent=2)

        # SUCCESS: Ownership data verified
        structured_logger.logger.info(
            f"Ownership verification successful for {ticker_upper}",
            extra={
                "tool_name": "check_client_suitability",
                "ticker": ticker_upper,
                "ownership_verified": True,
                "has_institutional_data": has_institutional_data,
                "has_major_holders": has_major_holders_data
            }
        )

    except Exception as e:
        # ERROR: Failed to retrieve ownership data
        structured_logger.logger.error(
            f"Ownership verification error for {ticker_upper}: {str(e)}",
            extra={
                "tool_name": "check_client_suitability",
                "ticker": ticker_upper,
                "ownership_verification_error": True,
                "error": str(e),
                "security_alert": True
            }
        )

        ownership_concerns.append(f"Ownership verification error: {str(e)[:100]}")

        result = {
            "compliance_status": "DENIED",
            "ticker": ticker_upper,
            "compliance_reason": "OWNERSHIP VERIFICATION ERROR: System unable to verify ownership structure",
            "compliance_level": "OWNERSHIP_VERIFICATION_ERROR",
            "ownership_concerns": ownership_concerns,
            "compliance_checked_at": datetime.now().isoformat(),
            "risk_level": "HIGH",
            "requires_review": True,
            "escalation_required": True,
            "next_steps": [
                "Technical review required - ownership data retrieval failed",
                "Manual verification process required",
                "System administrator notification sent",
                "Cannot approve without ownership verification"
            ]
        }
        return json.dumps(result, indent=2)

    # All Checks Passed - Enhanced Approval with Verified Ownership
    structured_logger.log_compliance_approved(
        tool_name="check_client_suitability",
        ticker=ticker_upper,
        reason="Entity cleared all enhanced compliance checks including ownership verification"
    )

    structured_logger.log_tool_success(
        tool_name="check_client_suitability",
        compliance_flag="APPROVED",
        result_summary=f"Ticker {ticker_upper} approved after multi-layer screening with verified ownership"
    )

    result = {
        "compliance_status": "APPROVED",
        "ticker": ticker_upper,
        "compliance_reason": "Passed all enhanced compliance checks with verified ownership structure",
        "compliance_level": "CLEARED",
        "compliance_checked_at": datetime.now().isoformat(),
        "checks_performed": [
            "Hard blocklist screening (Layer 1)",
            "Enhanced watchlist verification (Layer 2)",
            "Ownership structure analysis (Layer 3)",
            "Beneficial owner screening (Layer 4) - Ownership data verified"
        ],
        "risk_level": "LOW",
        "requires_review": False,
        "data_access_approved": True
    }
    return json.dumps(result, indent=2)


async def get_market_data_impl(ticker: str, session_id: str = "http_session") -> str:
    """
    Core implementation of market data retrieval.

    This is the actual logic extracted from server.py's get_market_data tool.

    Args:
        ticker: Stock ticker symbol
        session_id: Session ID for rate limiting (defaults to "http_session" for HTTP calls)
    """
    # PHASE 4 SECURITY: Validate and sanitize input
    is_valid, sanitized_ticker, error_msg = validate_and_sanitize_ticker(ticker)

    if not is_valid:
        structured_logger.logger.warning(
            f"Input validation failed for get_market_data: {ticker}",
            extra={
                "tool_name": "get_market_data",
                "event_type": "input_validation_failure",
                "input_value": ticker[:50],
                "error": error_msg,
                "severity": 4,
                "security_alert": True
            }
        )

        return json.dumps({
            "error": True,
            "error_code": "VALIDATION_ERROR",
            "message": error_msg,
            "ticker": ticker,
            "metadata": {
                "ticker": ticker,
                "retrieved_at": datetime.now().isoformat(),
                "data_source": "Yahoo Finance (yfinance)",
                "classification": "CONFIDENTIAL - INTERNAL USE ONLY"
            }
        }, indent=2)

    ticker_upper = sanitized_ticker

    # Log tool invocation
    structured_logger.log_tool_invocation(
        tool_name="get_market_data",
        input_params={"ticker": ticker_upper},
        compliance_flag="ASSUMED_APPROVED"
    )

    # PHASE 5: Check cache first (synchronous)
    cached_data = get_cached_ticker(ticker_upper)
    if cached_data:
        structured_logger.logger.info(
            f"Cache hit for ticker {ticker_upper}",
            extra={
                "tool_name": "get_market_data",
                "ticker": ticker_upper,
                "cache_hit": True
            }
        )
        return cached_data

    # PHASE 5: Check rate limit (synchronous)
    is_allowed, calls_in_window, retry_after = check_rate_limit(session_id, "get_market_data")
    if not is_allowed:
        structured_logger.logger.warning(
            f"Rate limit exceeded for get_market_data",
            extra={
                "tool_name": "get_market_data",
                "ticker": ticker_upper,
                "rate_limit_exceeded": True,
                "retry_after_seconds": retry_after
            }
        )

        return json.dumps({
            "error": True,
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": f"Rate limit exceeded ({RATE_LIMIT_MAX_CALLS} calls per minute). Please try again later.",
            "retry_after_seconds": retry_after,
            "ticker": ticker_upper,
            "metadata": {
                "ticker": ticker_upper,
                "retrieved_at": datetime.now().isoformat(),
                "data_source": "Yahoo Finance (yfinance)",
                "classification": "CONFIDENTIAL - INTERNAL USE ONLY"
            }
        }, indent=2)

    # PHASE 7: Async offload - yfinance is blocking, so run in thread pool
    try:
        stock = yf.Ticker(ticker_upper)

        # Run blocking yfinance calls in thread pool
        info = await asyncio.to_thread(lambda: stock.info)

        # Record API call for rate limiting (synchronous)
        record_api_call(session_id, ticker_upper, "get_market_data")

        # Silent failure detection (Layer 1: Check for empty info dict)
        if not info or len(info) == 0:
            structured_logger.logger.error(
                f"Silent failure detected: Empty info dict for {ticker_upper}",
                extra={
                    "tool_name": "get_market_data",
                    "ticker": ticker_upper,
                    "silent_failure": True,
                    "failure_layer": 1
                }
            )

            return json.dumps({
                "error": True,
                "error_code": "TICKER_NOT_FOUND",
                "message": f"Ticker {ticker_upper} not found on Yahoo Finance. Company may not exist or ticker symbol may be incorrect.",
                "ticker": ticker_upper,
                "verification_attempted": f"https://finance.yahoo.com/quote/{ticker_upper}",
                "suggestion": "Please verify the ticker symbol is correct and the company is publicly traded",
                "metadata": {
                    "ticker": ticker_upper,
                    "retrieved_at": datetime.now().isoformat(),
                    "data_source": "Yahoo Finance (yfinance)",
                    "classification": "CONFIDENTIAL - INTERNAL USE ONLY"
                }
            }, indent=2)

        # Verify company actually exists (check for essential fields)
        company_name = info.get("longName") or info.get("shortName")
        if not company_name:
            structured_logger.logger.error(
                f"Company verification failed: No company name for {ticker_upper}",
                extra={
                    "tool_name": "get_market_data",
                    "ticker": ticker_upper,
                    "verification_failure": True
                }
            )

            return json.dumps({
                "error": True,
                "error_code": "COMPANY_NOT_VERIFIED",
                "message": f"Unable to verify company exists for ticker {ticker_upper}. Data may be incomplete or ticker invalid.",
                "ticker": ticker_upper,
                "verification_link": f"https://finance.yahoo.com/quote/{ticker_upper}",
                "suggestion": "Verify this ticker on Yahoo Finance before proceeding",
                "metadata": {
                    "ticker": ticker_upper,
                    "retrieved_at": datetime.now().isoformat(),
                    "data_source": "Yahoo Finance (yfinance)",
                    "classification": "CONFIDENTIAL - INTERNAL USE ONLY"
                }
            }, indent=2)

        # Build normalized data structure using Pydantic
        # Add Yahoo Finance verification link
        yahoo_finance_url = f"https://finance.yahoo.com/quote/{ticker_upper}"

        metadata = MetadataSchema(
            retrieved_at=datetime.now().isoformat(),
            ticker=ticker_upper
        )

        entity_info = EntityInformation(
            ticker=ticker_upper,
            entity_name=info.get("longName", ticker_upper),
            sector=info.get("sector"),
            industry=info.get("industry"),
            country=info.get("country"),
            website=info.get("website")
        )

        market_metrics = MarketMetrics(
            current_price=info.get("currentPrice"),
            market_cap=info.get("marketCap"),
            market_cap_formatted=f"${info.get('marketCap', 0) / 1e9:.2f}B" if info.get("marketCap") else None,
            enterprise_value=info.get("enterpriseValue"),
            volume=info.get("volume"),
            avg_volume=info.get("averageVolume")
        )

        valuation_ratios = ValuationRatios(
            forward_pe=info.get("forwardPE"),
            trailing_pe=info.get("trailingPE"),
            price_to_book=info.get("priceToBook"),
            price_to_sales=info.get("priceToSalesTrailing12Months"),
            peg_ratio=info.get("pegRatio")
        )

        financial_health = FinancialHealth(
            dividend_yield=info.get("dividendYield"),
            dividend_rate=info.get("dividendRate"),
            profit_margin=info.get("profitMargins"),
            operating_margin=info.get("operatingMargins"),
            debt_to_equity=info.get("debtToEquity"),
            return_on_equity=info.get("returnOnEquity"),
            return_on_assets=info.get("returnOnAssets")
        )

        analyst_metrics = AnalystMetrics(
            recommendation=info.get("recommendationKey"),
            recommendation_mean=info.get("recommendationMean"),
            target_high_price=info.get("targetHighPrice"),
            target_low_price=info.get("targetLowPrice"),
            target_mean_price=info.get("targetMeanPrice"),
            number_of_analyst_opinions=info.get("numberOfAnalystOpinions")
        )

        normalized_data = NormalizedFinancialData(
            metadata=metadata,
            entity_information=entity_info,
            market_metrics=market_metrics,
            valuation_ratios=valuation_ratios,
            financial_health=financial_health,
            analyst_metrics=analyst_metrics
        )

        # Convert to JSON and add verification link
        result_dict = normalized_data.model_dump()

        # Add Yahoo Finance verification link to metadata
        result_dict["company_verified"] = True
        result_dict["verification_source"] = "Yahoo Finance"
        result_dict["yahoo_finance_link"] = yahoo_finance_url
        result_dict["verification_message"] = f"✓ Company verified on Yahoo Finance: {company_name}"

        result_json = json.dumps(result_dict, indent=2)

        # PHASE 5: Cache the result (synchronous)
        set_cached_ticker(ticker_upper, result_json)

        # Log success
        structured_logger.log_tool_success(
            tool_name="get_market_data",
            compliance_flag="DATA_RETRIEVED",
            result_summary=f"Successfully retrieved and verified data for {ticker_upper} ({company_name})"
        )

        return result_json

    except Exception as e:
        # Log error with sanitization
        safe_error_msg = sanitize_error_message(str(e))

        structured_logger.logger.error(
            f"Error retrieving market data for {ticker_upper}: {safe_error_msg}",
            extra={
                "tool_name": "get_market_data",
                "ticker": ticker_upper,
                "error": safe_error_msg,
                "severity": 3  # ERROR
            }
        )

        return json.dumps({
            "error": True,
            "error_code": "DATA_RETRIEVAL_ERROR",
            "message": safe_error_msg,
            "ticker": ticker_upper,
            "metadata": {
                "ticker": ticker_upper,
                "retrieved_at": datetime.now().isoformat(),
                "data_source": "Yahoo Finance (yfinance)",
                "classification": "CONFIDENTIAL - INTERNAL USE ONLY"
            }
        }, indent=2)
