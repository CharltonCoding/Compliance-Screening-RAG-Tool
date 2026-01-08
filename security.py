#!/usr/bin/env python3
"""
Phase 4: Defensive Security - Input Sanitization and Redaction
==============================================================

This module provides:
1. Regex-based input validation for ticker symbols
2. Redaction filters to scrub sensitive data from error messages
3. Defense against prompt injection attacks
4. Protection against data leakage

Security Principles:
- Validate all inputs against strict patterns
- Sanitize all outputs before returning to user
- Fail securely with safe error messages
- Log all security events
"""

import re
from typing import Optional, Any
from pydantic import BaseModel, Field, validator, ValidationError
from logging_config import structured_logger


# ============================================================================
# VALIDATION PATTERNS
# ============================================================================

# Strict ticker symbol validation: 1-5 uppercase letters only
TICKER_PATTERN = re.compile(r'^[A-Z]{1,5}$')

# Patterns to detect potential prompt injection attempts
PROMPT_INJECTION_PATTERNS = [
    re.compile(r'ignore\s+(previous|above|all)\s+(instructions|prompts)', re.IGNORECASE),
    re.compile(r'system\s*[:=]\s*["\']', re.IGNORECASE),
    re.compile(r'<\s*script\s*>', re.IGNORECASE),
    re.compile(r'```.*?```', re.DOTALL),  # Code blocks in ticker input
    re.compile(r'\{.*?\}', re.DOTALL),   # JSON objects in ticker input
]


# ============================================================================
# REDACTION PATTERNS
# ============================================================================

# Patterns to redact sensitive information from error messages
SENSITIVE_PATTERNS = [
    # API Keys (various formats)
    (re.compile(r'["\']?api[_-]?key["\']?\s*[:=]\s*["\']?([A-Za-z0-9_\-]{20,})["\']?', re.IGNORECASE),
     'api_key=***REDACTED***'),

    # Bearer tokens
    (re.compile(r'Bearer\s+([A-Za-z0-9_\-\.]{20,})', re.IGNORECASE),
     'Bearer ***REDACTED***'),

    # AWS-style keys
    (re.compile(r'(AKIA[0-9A-Z]{16})', re.IGNORECASE),
     '***REDACTED_AWS_KEY***'),

    # File paths (Unix and Windows)
    (re.compile(r'/(?:home|root|Users)/[^\s]+'),
     '***REDACTED_PATH***'),
    (re.compile(r'[A-Z]:\\(?:Users|Windows|Program Files)[^\s]*', re.IGNORECASE),
     '***REDACTED_PATH***'),

    # Email addresses
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
     '***REDACTED_EMAIL***'),

    # IP addresses
    (re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
     '***REDACTED_IP***'),

    # Passwords in error messages
    (re.compile(r'password["\']?\s*[:=]\s*["\']?([^\s"\']+)["\']?', re.IGNORECASE),
     'password=***REDACTED***'),

    # Database connection strings
    (re.compile(r'(postgres|mysql|mongodb)://[^\s]+', re.IGNORECASE),
     '***REDACTED_DB_CONNECTION***'),
]


# ============================================================================
# VALIDATION MODELS
# ============================================================================

class ValidatedTickerInput(BaseModel):
    """
    Validated ticker input with strict regex pattern enforcement.

    Security Features:
    - Only accepts 1-5 uppercase letters
    - Automatically converts lowercase to uppercase
    - Detects prompt injection attempts
    - Logs validation failures for security monitoring
    """
    ticker: str = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Stock ticker symbol (1-5 uppercase letters only)"
    )

    @validator('ticker')
    def validate_ticker_format(cls, v: str) -> str:
        """
        Validate ticker symbol against strict pattern.

        Security Checks:
        1. Convert to uppercase
        2. Check for prompt injection patterns
        3. Validate against ^[A-Z]{1,5}$ regex
        4. Log security events
        """
        # Normalize to uppercase
        ticker_upper = v.strip().upper()

        # Check for prompt injection attempts
        for pattern in PROMPT_INJECTION_PATTERNS:
            if pattern.search(v):
                structured_logger.logger.warning(
                    "Potential prompt injection detected in ticker input",
                    extra={
                        "event_type": "security_validation_failure",
                        "failure_type": "PROMPT_INJECTION_ATTEMPT",
                        "input_value": v[:50],  # Truncate for logging
                        "severity": 4,  # WARNING
                        "security_alert": True
                    }
                )
                raise ValueError(
                    f"Invalid ticker format: '{v}'. "
                    "Ticker symbols must be 1-5 uppercase letters only (e.g., 'AAPL', 'MSFT', 'JPM')."
                )

        # Validate against strict pattern
        if not TICKER_PATTERN.match(ticker_upper):
            structured_logger.logger.warning(
                f"Ticker validation failed: {ticker_upper}",
                extra={
                    "event_type": "input_validation_failure",
                    "failure_type": "INVALID_TICKER_FORMAT",
                    "input_value": ticker_upper,
                    "severity": 4  # WARNING
                }
            )
            raise ValueError(
                f"Invalid ticker format: '{ticker_upper}'. "
                "Ticker symbols must be 1-5 uppercase letters only (e.g., 'AAPL', 'MSFT', 'JPM'). "
                f"Received: '{v}'"
            )

        # Validation passed
        structured_logger.logger.info(
            f"Ticker validation passed: {ticker_upper}",
            extra={
                "event_type": "input_validation_success",
                "ticker": ticker_upper,
                "severity": 6  # INFORMATIONAL
            }
        )

        return ticker_upper


# ============================================================================
# SANITIZATION FUNCTIONS
# ============================================================================

def sanitize_ticker_input(ticker: str) -> tuple[bool, str, Optional[str]]:
    """
    Sanitize and validate ticker input.

    Args:
        ticker: Raw ticker input string

    Returns:
        Tuple of (is_valid, sanitized_ticker, error_message)
        - is_valid: True if validation passed
        - sanitized_ticker: Cleaned and validated ticker symbol
        - error_message: Human-readable error if validation failed
    """
    try:
        validated = ValidatedTickerInput(ticker=ticker)
        return True, validated.ticker, None
    except ValidationError as e:
        # Extract user-friendly error message
        error_msg = "Invalid ticker input. "
        for error in e.errors():
            if 'msg' in error:
                error_msg += error['msg']
            elif 'ctx' in error and 'error' in error['ctx']:
                error_msg += str(error['ctx']['error'])

        structured_logger.logger.warning(
            f"Ticker sanitization failed: {ticker}",
            extra={
                "event_type": "sanitization_failure",
                "input_value": ticker[:50],
                "error": error_msg,
                "severity": 4  # WARNING
            }
        )

        return False, ticker, error_msg
    except Exception as e:
        return False, ticker, f"Validation error: {str(e)}"


def redact_sensitive_data(text: str) -> str:
    """
    Redact sensitive information from text before returning to user.

    This prevents accidental leakage of:
    - API keys
    - File paths
    - Tokens
    - IP addresses
    - Email addresses
    - Database connection strings

    Args:
        text: Text that may contain sensitive information

    Returns:
        Text with sensitive information redacted
    """
    redacted_text = text

    # Apply all redaction patterns
    for pattern, replacement in SENSITIVE_PATTERNS:
        redacted_text = pattern.sub(replacement, redacted_text)

    return redacted_text


def sanitize_error_message(error: Exception, ticker: str = "UNKNOWN") -> str:
    """
    Sanitize error messages before returning to user.

    Security Features:
    - Redacts sensitive data (API keys, paths, etc.)
    - Converts technical errors to user-friendly messages
    - Logs original error securely
    - Returns safe error message

    Args:
        error: Original exception
        ticker: Ticker symbol associated with error

    Returns:
        Safe, redacted error message
    """
    # Log original error securely (not returned to user)
    structured_logger.logger.error(
        f"Error sanitization triggered: {type(error).__name__}",
        extra={
            "event_type": "error_sanitization",
            "ticker": ticker,
            "error_type": type(error).__name__,
            "error_detail": str(error)[:200],  # Truncate for logging
            "severity": 3  # ERROR
        }
    )

    # Get error message and redact sensitive data
    error_message = str(error)
    redacted_message = redact_sensitive_data(error_message)

    # If redaction occurred, log it
    if redacted_message != error_message:
        structured_logger.logger.warning(
            "Sensitive data redacted from error message",
            extra={
                "event_type": "redaction_applied",
                "ticker": ticker,
                "severity": 4,  # WARNING
                "security_alert": True
            }
        )

    return redacted_message


# ============================================================================
# SECURITY VALIDATION WRAPPER
# ============================================================================

def validate_and_sanitize_ticker(ticker: str) -> tuple[bool, str, Optional[str]]:
    """
    Complete security validation and sanitization pipeline.

    This is the main entry point for ticker validation.

    Security Pipeline:
    1. Input sanitization and validation
    2. Prompt injection detection
    3. Format validation (^[A-Z]{1,5}$)
    4. Security event logging

    Args:
        ticker: Raw ticker input

    Returns:
        Tuple of (is_valid, sanitized_ticker, error_message)
    """
    return sanitize_ticker_input(ticker)


# ============================================================================
# TESTING HELPERS
# ============================================================================

def test_security_validation():
    """
    Test suite for security validation.
    Run with: python -c "from security import test_security_validation; test_security_validation()"
    """
    print("=" * 80)
    print("SECURITY VALIDATION TEST SUITE")
    print("=" * 80)

    test_cases = [
        # Valid tickers
        ("AAPL", True, "Valid: Apple"),
        ("MSFT", True, "Valid: Microsoft"),
        ("JPM", True, "Valid: JPMorgan"),
        ("GS", True, "Valid: Goldman Sachs"),
        ("A", True, "Valid: Single letter"),
        ("GOOGL", True, "Valid: 5 letters"),

        # Invalid tickers - format
        ("TOOLONG", False, "Invalid: Too long (6+ chars)"),
        ("", False, "Invalid: Empty string"),
        ("123", False, "Invalid: Numbers only"),
        ("AAPL123", False, "Invalid: Contains numbers"),
        ("AA-PL", False, "Invalid: Contains hyphen"),
        ("AA.PL", False, "Invalid: Contains dot"),
        ("AAPL ", False, "Invalid: Trailing space (should be stripped)"),
        (" AAPL", False, "Invalid: Leading space (should be stripped)"),

        # Potential prompt injection
        ("ignore previous instructions", False, "Security: Prompt injection"),
        ("system: 'admin'", False, "Security: System prompt"),
        ("<script>", False, "Security: XSS attempt"),
        ("```python\nprint('hack')```", False, "Security: Code block"),
        ('{"key": "value"}', False, "Security: JSON injection"),

        # Case conversion
        ("aapl", True, "Valid: Lowercase converted to uppercase"),
        ("MsFt", True, "Valid: Mixed case converted"),
    ]

    print("\n🧪 Running test cases...\n")

    passed = 0
    failed = 0

    for ticker_input, should_pass, description in test_cases:
        is_valid, sanitized, error_msg = validate_and_sanitize_ticker(ticker_input)

        if is_valid == should_pass:
            status = "✓ PASS"
            passed += 1
        else:
            status = "✗ FAIL"
            failed += 1

        print(f"{status} | {description}")
        print(f"       Input: '{ticker_input}' → Valid: {is_valid}, Sanitized: '{sanitized}'")
        if error_msg:
            print(f"       Error: {error_msg[:80]}")
        print()

    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)

    # Test redaction
    print("\n" + "=" * 80)
    print("REDACTION TEST SUITE")
    print("=" * 80 + "\n")

    redaction_tests = [
        ("Error: api_key=sk_live_1234567890abcdefghij", "Should redact API key"),
        ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "Should redact bearer token"),
        ("File not found: /home/user/secrets.txt", "Should redact file path"),
        ("Connection failed: postgres://user:pass@localhost/db", "Should redact DB string"),
        ("Contact: admin@company.com", "Should redact email"),
        ("Server IP: 192.168.1.100", "Should redact IP address"),
    ]

    for text, description in redaction_tests:
        redacted = redact_sensitive_data(text)
        print(f"🔒 {description}")
        print(f"   Original: {text}")
        print(f"   Redacted: {redacted}")
        print()

    print("=" * 80)
    print("TEST SUITE COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    test_security_validation()
