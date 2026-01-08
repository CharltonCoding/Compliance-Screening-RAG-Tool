#!/usr/bin/env python3
"""
Quick test to verify structured logging works and writes to files.
"""

from logging_config import structured_logger

# Generate session correlation ID
session_id = structured_logger.generate_correlation_id()
print(f"Session Correlation ID: {session_id}\n")

# Test 1: Tool invocation
print("Test 1: Logging tool invocation...")
structured_logger.log_tool_invocation(
    tool_name="check_client_suitability",
    input_params={"ticker": "AAPL"},
    compliance_flag="PENDING"
)
print("✓ Logged\n")

# Test 2: Compliance approved
print("Test 2: Logging compliance APPROVED...")
structured_logger.log_compliance_approved(
    tool_name="check_client_suitability",
    ticker="AAPL",
    reason="Entity cleared all compliance checks"
)
print("✓ Logged\n")

# Test 3: Compliance denied (SECURITY EVENT)
print("Test 3: Logging compliance DENIED (security event)...")
structured_logger.log_compliance_denied(
    tool_name="check_client_suitability",
    ticker="RESTRICTED",
    reason="Entity is on the Restricted Trading List"
)
print("✓ Logged to BOTH general log AND security-audit.log\n")

# Test 4: Silent failure
print("Test 4: Logging silent failure detection...")
structured_logger.log_silent_failure_detected(
    tool_name="get_market_data",
    ticker="NOTREAL",
    failure_type="INVALID_TICKER",
    detail="No pricing information available"
)
print("✓ Logged\n")

# Test 5: Data retrieval error
print("Test 5: Logging data retrieval error...")
structured_logger.log_data_retrieval_error(
    tool_name="get_market_data",
    ticker="TICKER1",
    error_code="NETWORK_ERROR",
    error_message="Unable to reach Yahoo Finance API"
)
print("✓ Logged\n")

# Test 6: Tool success
print("Test 6: Logging tool success...")
structured_logger.log_tool_success(
    tool_name="get_market_data",
    compliance_flag="N/A",
    result_summary="Successfully retrieved market data for AAPL"
)
print("✓ Logged\n")

print("=" * 80)
print("ALL TESTS COMPLETED")
print("=" * 80)
print("\nNow check the log files:")
print("  cat logs/mcp-server.log | python -m json.tool | less")
print("  cat logs/security-audit.log | python -m json.tool | less")
print("\nOr analyze them:")
print("  python analyze_logs.py")
