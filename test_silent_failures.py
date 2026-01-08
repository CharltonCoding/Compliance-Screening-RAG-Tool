#!/usr/bin/env python3
"""
Test script to demonstrate silent failure detection in get_market_data.

This script shows how the refactored tool handles various failure scenarios
that would previously result in hallucinations or partial data.
"""

import json
import yfinance as yf
from datetime import datetime
from server import (
    NormalizedFinancialData, DataRetrievalError,
    MetadataSchema, EntityInformation, MarketMetrics,
    ValuationRatios, FinancialHealth, AnalystMetrics
)

def get_market_data_direct(ticker: str) -> str:
    """
    Direct implementation of get_market_data logic for testing.
    This is the same logic as in server.py but callable outside MCP context.
    """
    retrieved_at = datetime.now().isoformat()
    ticker_upper = ticker.upper()

    try:
        # Fetch data from yfinance
        stock = yf.Ticker(ticker)
        info = stock.info

        # SILENT FAILURE DETECTION #1: Check if info dictionary is suspiciously empty
        if not info or len(info) < 5:
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
                error = DataRetrievalError(
                    error_code="INSUFFICIENT_DATA",
                    ticker=ticker_upper,
                    message=f"Data quality check failed: {reason}",
                    detail="Retrieved data does not meet minimum quality thresholds for reliable analysis",
                    troubleshooting="The ticker may be valid but data is incomplete. Try again later or verify the security is actively traded with sufficient analyst coverage.",
                    retrieved_at=retrieved_at
                )
                return error.model_dump_json(indent=2)

            # Data is valid - return normalized response
            return normalized_data.model_dump_json(indent=2)

        except Exception as validation_error:
            # Pydantic validation failed
            error = DataRetrievalError(
                error_code="UNKNOWN_ERROR",
                ticker=ticker_upper,
                message="Data validation failed during normalization",
                detail=str(validation_error),
                troubleshooting="Data from source could not be validated. This may indicate corrupted or malformed data.",
                retrieved_at=retrieved_at
            )
            return error.model_dump_json(indent=2)

    except Exception as e:
        # Network or other unexpected errors
        error = DataRetrievalError(
            error_code="NETWORK_ERROR",
            ticker=ticker_upper,
            message=f"Unable to retrieve entity data for {ticker_upper}",
            detail=str(e),
            troubleshooting="Check network connectivity. Verify Yahoo Finance API is accessible. Review Claude Desktop MCP logs for details.",
            retrieved_at=retrieved_at
        )
        return error.model_dump_json(indent=2)

def print_result(ticker: str, description: str):
    """Helper to print formatted results"""
    print(f"\n{'='*80}")
    print(f"TEST: {description}")
    print(f"Ticker: {ticker}")
    print(f"{'='*80}")

    result = get_market_data_direct(ticker)
    result_dict = json.loads(result)

    # Check if it's an error response
    if result_dict.get("error"):
        print(f"✗ ERROR DETECTED: {result_dict['error_code']}")
        print(f"  Message: {result_dict['message']}")
        print(f"  Detail: {result_dict.get('detail', 'N/A')}")
        print(f"  Troubleshooting: {result_dict['troubleshooting'][:80]}...")
    else:
        print(f"✓ SUCCESS: Data retrieved")
        print(f"  Entity: {result_dict['entity_information']['entity_name']}")
        print(f"  Price: ${result_dict['market_metrics']['current_price']}")
        print(f"  Market Cap: {result_dict['market_metrics']['market_cap_formatted']}")

        # Check data quality
        ratios = result_dict['valuation_ratios']
        valid_ratios = sum(1 for v in ratios.values() if v is not None)
        print(f"  Valuation Ratios: {valid_ratios}/5 populated")

def main():
    """Run test scenarios"""
    print("SILENT FAILURE DETECTION TEST SUITE")
    print("This demonstrates how the tool prevents hallucinations")

    # Test 1: Valid major ticker (should succeed)
    print_result("AAPL", "Valid major ticker - Apple Inc.")

    # Test 2: Invalid ticker (should fail with INVALID_TICKER)
    print_result("NOTAREALTICKER", "Invalid ticker - should detect missing price data")

    # Test 3: Valid but potentially incomplete ticker
    # (Some penny stocks or OTC securities may have incomplete data)
    print_result("ZZZZ", "Edge case ticker - may have insufficient data")

    # Test 4: Foreign exchange ticker (different data structure)
    print_result("EURUSD=X", "Currency pair - EUR/USD")

    print(f"\n{'='*80}")
    print("TEST SUITE COMPLETE")
    print(f"{'='*80}")
    print("\nKey Takeaways:")
    print("1. Valid tickers return comprehensive structured data")
    print("2. Invalid tickers return explicit error codes (not partial data)")
    print("3. Data quality is validated before being returned to the AI")
    print("4. Error messages include troubleshooting guidance")
    print("\nThis prevents the AI from:")
    print("- Making up numbers when data is missing")
    print("- Analyzing incomplete or throttled responses")
    print("- Confusing API errors with valid securities")

if __name__ == "__main__":
    main()
