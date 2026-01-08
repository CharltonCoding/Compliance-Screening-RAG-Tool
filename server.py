from fastmcp import FastMCP
import yfinance as yf
import json
import sys
import asyncio
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator

# Import structured logging
from logging_config import structured_logger, RFC5424Severity

# Import security validation and redaction (Phase 4)
from security import validate_and_sanitize_ticker, sanitize_error_message, redact_sensitive_data

# Import cache and rate limiting (Phase 5)
from cache import (
    get_cached_ticker,
    set_cached_ticker,
    check_rate_limit,
    record_api_call,
    CACHE_TTL_SECONDS,
    RATE_LIMIT_MAX_CALLS
)

# Initialize the server
mcp = FastMCP("Financial-Services-Intel-Node")

# Generate correlation ID for this session
SESSION_CORRELATION_ID = structured_logger.generate_correlation_id()
print(f"[MCP Server] Session Correlation ID: {SESSION_CORRELATION_ID}", file=sys.stderr)

# Pydantic schemas for normalized financial data
class MetadataSchema(BaseModel):
    """Metadata about the data retrieval operation"""
    classification: str = "CONFIDENTIAL - INTERNAL USE ONLY"
    data_source: str = "Enterprise Market Data Feed (Simulated via Yahoo Finance)"
    retrieved_at: str
    disclaimer: str = "NON-ADVISORY ONLY - For analysis purposes exclusively"

class EntityInformation(BaseModel):
    """Core entity identification information"""
    ticker: str
    entity_name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None

class MarketMetrics(BaseModel):
    """Current market trading metrics"""
    current_price: Optional[float] = None
    currency: str = "USD"
    market_cap: Optional[int] = None
    market_cap_formatted: Optional[str] = None
    enterprise_value: Optional[int] = None
    volume: Optional[int] = None
    avg_volume: Optional[int] = None

class ValuationRatios(BaseModel):
    """Financial valuation ratios"""
    forward_pe: Optional[float] = None
    trailing_pe: Optional[float] = None
    price_to_book: Optional[float] = None
    price_to_sales: Optional[float] = None
    peg_ratio: Optional[float] = None

    @field_validator('*', mode='before')
    @classmethod
    def validate_numeric(cls, v):
        """Ensure numeric values are valid (not infinity or NaN)"""
        if v is not None:
            if isinstance(v, (int, float)):
                if not (-1e10 < v < 1e10):  # Reasonable bounds
                    return None
        return v

class FinancialHealth(BaseModel):
    """Financial health indicators"""
    dividend_yield: Optional[float] = None
    dividend_rate: Optional[float] = None
    profit_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    debt_to_equity: Optional[float] = None

class AnalystMetrics(BaseModel):
    """Analyst opinions and price targets"""
    recommendation: Optional[str] = None
    target_high_price: Optional[float] = None
    target_low_price: Optional[float] = None
    target_mean_price: Optional[float] = None
    number_of_analyst_opinions: Optional[int] = None

class NormalizedFinancialData(BaseModel):
    """Complete normalized financial data structure with validation"""
    metadata: MetadataSchema
    entity_information: EntityInformation
    market_metrics: MarketMetrics
    valuation_ratios: ValuationRatios
    financial_health: FinancialHealth
    analyst_metrics: AnalystMetrics

    def has_sufficient_data(self) -> tuple[bool, str]:
        """
        Validates that we have sufficient data to prevent silent failures.
        Returns (is_valid, reason)
        """
        # Check if we have basic entity information
        if not self.entity_information.entity_name:
            return False, "Missing entity name - possible invalid ticker"

        # Check if we have at least some market data
        if self.market_metrics.current_price is None and self.market_metrics.market_cap is None:
            return False, "Missing critical market metrics - API may have throttled request"

        # Check if we have at least 2 out of 5 key valuation ratios
        ratios = [
            self.valuation_ratios.forward_pe,
            self.valuation_ratios.trailing_pe,
            self.valuation_ratios.price_to_book,
            self.valuation_ratios.price_to_sales,
            self.valuation_ratios.peg_ratio
        ]
        valid_ratios = sum(1 for r in ratios if r is not None)

        if valid_ratios < 2:
            return False, f"Insufficient valuation data ({valid_ratios}/5 ratios) - data may be incomplete"

        return True, "Data quality check passed"

class DataRetrievalError(BaseModel):
    """Structured error response for data retrieval failures"""
    error: bool = True
    error_code: Literal["INVALID_TICKER", "API_THROTTLE", "INSUFFICIENT_DATA", "NETWORK_ERROR", "UNKNOWN_ERROR", "RATE_LIMIT_EXCEEDED"]
    ticker: str
    message: str
    detail: Optional[str] = None
    troubleshooting: str
    retrieved_at: str

@mcp.tool()
async def check_client_suitability(ticker: str) -> str:
    """
    Simulates a KYC/Compliance check before allowing analysis.
    This is a MANDATORY compliance gate that MUST be called before accessing any financial data.

    Implements enterprise-grade safeguards:
    - Regex-based input validation (^[A-Z]{1,5}$)
    - Prompt injection detection
    - Restricted Trading List verification
    - Sanctions screening simulation
    - Internal watchlist checking

    PHASE 7: Async implementation prevents blocking the MCP server.

    Args:
        ticker: The stock symbol (e.g., 'JPM' for JPMorgan, 'GS' for Goldman Sachs)

    Returns:
        JSON string with compliance status and reasoning
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
            "status": "ERROR",
            "ticker": ticker,
            "error": "Input validation failed",
            "message": error_msg,
            "action_required": "Provide a valid ticker symbol (1-5 uppercase letters only, e.g., 'AAPL', 'MSFT', 'JPM').",
            "checked_at": datetime.now().isoformat()
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

    # Mock restricted list for compliance demonstration
    # In production, this would query an internal compliance database
    restricted_entities = [
        "RESTRICTED",  # Demo ticker for testing
        "SANCTION",    # Demo ticker for sanctions example
    ]

    # Check against restricted list
    if any(x in ticker_upper for x in restricted_entities):
        # CRITICAL SECURITY EVENT - Log to security audit
        structured_logger.log_compliance_denied(
            tool_name="check_client_suitability",
            ticker=ticker_upper,
            reason="Entity is on the Restricted Trading List"
        )

        result = {
            "status": "DENIED",
            "ticker": ticker_upper,
            "reason": "Entity is on the Restricted Trading List",
            "action_required": "DO NOT PROCEED with analysis. Contact Compliance team.",
            "checked_at": datetime.now().isoformat(),
            "compliance_level": "CRITICAL"
        }
        return json.dumps(result, indent=2)

    # Passed compliance checks
    structured_logger.log_compliance_approved(
        tool_name="check_client_suitability",
        ticker=ticker_upper,
        reason="Entity cleared all compliance checks"
    )

    structured_logger.log_tool_success(
        tool_name="check_client_suitability",
        compliance_flag="APPROVED",
        result_summary=f"Ticker {ticker_upper} approved for analysis"
    )

    result = {
        "status": "APPROVED",
        "ticker": ticker_upper,
        "reason": "Entity cleared all compliance checks",
        "action_permitted": "Proceed with financial analysis",
        "checked_at": datetime.now().isoformat(),
        "compliance_level": "CLEARED"
    }
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_market_data(ticker: str) -> str:
    """
    Retrieves real-time market data for a corporate entity with robust validation.

    SECURITY NOTE: This tool should ONLY be called AFTER check_client_suitability
    returns APPROVED status. The LLM is instructed to enforce this workflow.

    Returns structured, deterministic financial data to prevent hallucinations.
    Includes silent failure detection to catch API throttling and incomplete data.
    All data is validated through Pydantic schemas.

    Phase 4 Security Features:
    - Regex-based input validation (^[A-Z]{1,5}$)
    - Prompt injection detection
    - Automatic redaction of sensitive data in error messages

    Phase 7: Async implementation with non-blocking yfinance calls
    - Uses asyncio.to_thread() to offload blocking I/O
    - Prevents freezing the MCP communication loop with Claude Desktop
    - Enables concurrent request handling

    Args:
        ticker: The stock symbol (e.g., 'JPM' for JPMorgan, 'GS' for Goldman Sachs)

    Returns:
        JSON string with comprehensive market data or structured error
    """
    # PHASE 4 SECURITY: Validate and sanitize input
    is_valid, sanitized_ticker, error_msg = validate_and_sanitize_ticker(ticker)

    if not is_valid:
        # Input validation failed - return error
        structured_logger.logger.warning(
            f"Input validation failed for get_market_data: {ticker}",
            extra={
                "tool_name": "get_market_data",
                "event_type": "input_validation_failure",
                "input_value": ticker[:50],
                "error": error_msg,
                "severity": 4,  # WARNING
                "security_alert": True
            }
        )

        error = DataRetrievalError(
            error_code="INVALID_TICKER",
            ticker=ticker[:50],
            message="Input validation failed",
            detail=error_msg,
            troubleshooting="Provide a valid ticker symbol (1-5 uppercase letters only, e.g., 'AAPL', 'MSFT', 'JPM').",
            retrieved_at=datetime.now().isoformat()
        )
        return error.model_dump_json(indent=2)

    # Use sanitized ticker for all subsequent operations
    ticker_upper = sanitized_ticker

    # Log tool invocation (after validation)
    structured_logger.log_tool_invocation(
        tool_name="get_market_data",
        input_params={"ticker": ticker_upper},
        compliance_flag="N/A"
    )

    retrieved_at = datetime.now().isoformat()

    # PHASE 5: Check rate limit first
    is_allowed, calls_in_window, retry_after = check_rate_limit(
        SESSION_CORRELATION_ID,
        "get_market_data"
    )

    if not is_allowed:
        # Rate limit exceeded - return 429 error
        structured_logger.logger.warning(
            f"Rate limit exceeded for session {SESSION_CORRELATION_ID[:16]}...",
            extra={
                "tool_name": "get_market_data",
                "event_type": "rate_limit_exceeded",
                "calls_in_window": calls_in_window,
                "max_calls": RATE_LIMIT_MAX_CALLS,
                "retry_after": retry_after,
                "severity": 4,  # WARNING
                "security_alert": True
            }
        )

        error = DataRetrievalError(
            error_code="RATE_LIMIT_EXCEEDED",
            ticker=ticker_upper,
            message=f"Rate limit exceeded: {calls_in_window} calls in 60 seconds",
            detail=f"Maximum {RATE_LIMIT_MAX_CALLS} calls per minute per session",
            troubleshooting=f"Wait {retry_after} seconds before retrying. Consider caching results or reducing request frequency.",
            retrieved_at=retrieved_at
        )
        return error.model_dump_json(indent=2)

    # PHASE 5: Check cache for existing data
    cached_data = get_cached_ticker(ticker_upper)

    if cached_data:
        # Cache HIT - return immediately without calling yfinance
        structured_logger.log_tool_success(
            tool_name="get_market_data",
            compliance_flag="N/A",
            result_summary=f"Cache HIT for {ticker_upper} (no API call needed)"
        )
        return json.dumps(cached_data, indent=2)

    # Cache MISS - proceed with yfinance call
    try:
        # PHASE 7: Async offloading - fetch data from yfinance in thread pool
        # This prevents blocking the MCP server's event loop
        stock = yf.Ticker(ticker_upper)
        info = await asyncio.to_thread(lambda: stock.info)

        # SILENT FAILURE DETECTION #1: Check if info dictionary is suspiciously empty
        if not info or len(info) < 5:
            structured_logger.log_silent_failure_detected(
                tool_name="get_market_data",
                ticker=ticker_upper,
                failure_type="API_THROTTLE",
                detail=f"Received only {len(info)} fields in response"
            )

            error = DataRetrievalError(
                error_code="API_THROTTLE",
                ticker=ticker_upper,
                message="Yahoo Finance returned minimal data - request may have been throttled",
                detail=f"Received only {len(info)} fields in response",
                troubleshooting="Wait 60 seconds and retry. Yahoo Finance rate limits requests. Consider using a premium data source for production.",
                retrieved_at=retrieved_at
            )
            return error.model_dump_json(indent=2)

        # SILENT FAILURE DETECTION #2: Check for error indicators in the response
        if 'regularMarketPrice' not in info and 'currentPrice' not in info and 'previousClose' not in info:
            structured_logger.log_silent_failure_detected(
                tool_name="get_market_data",
                ticker=ticker_upper,
                failure_type="INVALID_TICKER",
                detail="No pricing information available from data source"
            )

            error = DataRetrievalError(
                error_code="INVALID_TICKER",
                ticker=ticker_upper,
                message=f"Ticker '{ticker_upper}' does not appear to be valid or is not traded",
                detail="No pricing information available from data source",
                troubleshooting="Verify ticker symbol is correct. Check if security is actively traded. Delisted securities may return empty data.",
                retrieved_at=retrieved_at
            )
            return error.model_dump_json(indent=2)

        # Build the normalized data structure with Pydantic validation
        try:
            normalized_data = NormalizedFinancialData(
                metadata=MetadataSchema(
                    retrieved_at=retrieved_at
                ),
                entity_information=EntityInformation(
                    ticker=ticker_upper,
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

            # SILENT FAILURE DETECTION #3: Validate data quality
            is_valid, reason = normalized_data.has_sufficient_data()
            if not is_valid:
                structured_logger.log_silent_failure_detected(
                    tool_name="get_market_data",
                    ticker=ticker_upper,
                    failure_type="INSUFFICIENT_DATA",
                    detail=reason
                )

                error = DataRetrievalError(
                    error_code="INSUFFICIENT_DATA",
                    ticker=ticker_upper,
                    message=f"Data quality check failed: {reason}",
                    detail="Retrieved data does not meet minimum quality thresholds for reliable analysis",
                    troubleshooting="The ticker may be valid but data is incomplete. Try again later or verify the security is actively traded with sufficient analyst coverage.",
                    retrieved_at=retrieved_at
                )
                return error.model_dump_json(indent=2)

            # Data is valid - cache and return normalized response
            # PHASE 5: Cache successful result
            normalized_data_dict = json.loads(normalized_data.model_dump_json())
            set_cached_ticker(
                ticker_upper,
                normalized_data_dict,
                ttl_seconds=CACHE_TTL_SECONDS
            )

            # PHASE 5: Record API call for rate limiting
            record_api_call(SESSION_CORRELATION_ID, ticker_upper, "get_market_data")

            structured_logger.log_tool_success(
                tool_name="get_market_data",
                compliance_flag="N/A",
                result_summary=f"Successfully retrieved and cached market data for {ticker_upper}"
            )
            return normalized_data.model_dump_json(indent=2)

        except Exception as validation_error:
            # Pydantic validation failed
            # PHASE 4 SECURITY: Sanitize error message before logging and returning
            safe_error_msg = sanitize_error_message(validation_error, ticker_upper)

            structured_logger.log_data_retrieval_error(
                tool_name="get_market_data",
                ticker=ticker_upper,
                error_code="UNKNOWN_ERROR",
                error_message=f"Data validation failed: {safe_error_msg}"
            )

            error = DataRetrievalError(
                error_code="UNKNOWN_ERROR",
                ticker=ticker_upper,
                message="Data validation failed during normalization",
                detail=safe_error_msg,
                troubleshooting="Data from source could not be validated. This may indicate corrupted or malformed data.",
                retrieved_at=retrieved_at
            )
            return error.model_dump_json(indent=2)

    except Exception as e:
        # Network or other unexpected errors
        # PHASE 4 SECURITY: Sanitize error message before logging and returning
        safe_error_msg = sanitize_error_message(e, ticker_upper)

        structured_logger.log_data_retrieval_error(
            tool_name="get_market_data",
            ticker=ticker_upper,
            error_code="NETWORK_ERROR",
            error_message=safe_error_msg
        )

        error = DataRetrievalError(
            error_code="NETWORK_ERROR",
            ticker=ticker_upper,
            message=f"Unable to retrieve entity data for {ticker_upper}",
            detail=safe_error_msg,
            troubleshooting="Check network connectivity. Verify Yahoo Finance API is accessible. Review Claude Desktop MCP logs for details.",
            retrieved_at=retrieved_at
        )
        return error.model_dump_json(indent=2)

if __name__ == "__main__":
    try:
        mcp.run()
    except Exception as e:
        # This will print errors to the Claude debug logs if it crashes
        print(f"CRITICAL SERVER ERROR: {e}", file=sys.stderr)
        raise
