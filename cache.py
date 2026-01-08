#!/usr/bin/env python3
"""
Phase 5: Rate-Limit Management & Caching Layer
================================================

This module provides:
1. SQLite-based cache for ticker data (5-minute TTL)
2. Rate limit tracking per session/IP
3. Automatic cache invalidation
4. Protection against API bans

Cache Strategy:
- Cache successful ticker lookups for 5 minutes
- Track API call frequency per session
- Return 429 errors with retry_after when rate limited
- Log all cache hits/misses for monitoring
"""

import sqlite3
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from contextlib import contextmanager

from logging_config import structured_logger


# ============================================================================
# CACHE CONFIGURATION
# ============================================================================

CACHE_DB_PATH = Path("./cache/ticker_cache.db")
CACHE_TTL_SECONDS = 300  # 5 minutes
RATE_LIMIT_WINDOW_SECONDS = 60  # 1 minute
RATE_LIMIT_MAX_CALLS = 30  # 30 calls per minute per session


# ============================================================================
# DATABASE SETUP
# ============================================================================

def init_cache_db():
    """Initialize SQLite cache database with required tables"""
    CACHE_DB_PATH.parent.mkdir(exist_ok=True)

    conn = sqlite3.connect(CACHE_DB_PATH)
    cursor = conn.cursor()

    # Ticker data cache table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticker_cache (
            ticker TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            cached_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            hit_count INTEGER DEFAULT 0
        )
    """)

    # Rate limit tracking table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            session_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            ticker TEXT,
            tool_name TEXT NOT NULL
        )
    """)

    # Create index for efficient rate limit queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_rate_limits_session
        ON rate_limits(session_id, timestamp)
    """)

    conn.commit()
    conn.close()

    structured_logger.logger.info(
        "Cache database initialized",
        extra={
            "event_type": "cache_initialization",
            "cache_path": str(CACHE_DB_PATH),
            "severity": 6  # INFORMATIONAL
        }
    )


@contextmanager
def get_cache_connection():
    """Context manager for cache database connections"""
    conn = sqlite3.connect(CACHE_DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


# ============================================================================
# CACHE OPERATIONS
# ============================================================================

def get_cached_ticker(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached ticker data if available and not expired.

    Args:
        ticker: Stock ticker symbol (uppercase)

    Returns:
        Cached data dict or None if cache miss/expired
    """
    with get_cache_connection() as conn:
        cursor = conn.cursor()

        current_time = time.time()

        # Query for valid cached entry
        cursor.execute("""
            SELECT data, cached_at, expires_at, hit_count
            FROM ticker_cache
            WHERE ticker = ? AND expires_at > ?
        """, (ticker, current_time))

        row = cursor.fetchone()

        if row:
            data_json, cached_at, expires_at, hit_count = row

            # Update hit count
            cursor.execute("""
                UPDATE ticker_cache
                SET hit_count = hit_count + 1
                WHERE ticker = ?
            """, (ticker,))
            conn.commit()

            # Parse cached data
            cached_data = json.loads(data_json)

            # Calculate age
            age_seconds = current_time - cached_at
            ttl_remaining = expires_at - current_time

            # Log cache hit
            structured_logger.logger.info(
                f"Cache HIT for {ticker}",
                extra={
                    "event_type": "cache_hit",
                    "ticker": ticker,
                    "age_seconds": round(age_seconds, 2),
                    "ttl_remaining": round(ttl_remaining, 2),
                    "hit_count": hit_count + 1,
                    "severity": 6  # INFORMATIONAL
                }
            )

            return cached_data
        else:
            # Log cache miss
            structured_logger.logger.info(
                f"Cache MISS for {ticker}",
                extra={
                    "event_type": "cache_miss",
                    "ticker": ticker,
                    "severity": 6  # INFORMATIONAL
                }
            )

            return None


def set_cached_ticker(ticker: str, data: Dict[str, Any], ttl_seconds: int = CACHE_TTL_SECONDS):
    """
    Store ticker data in cache with TTL.

    Args:
        ticker: Stock ticker symbol (uppercase)
        data: Ticker data to cache (must be JSON-serializable)
        ttl_seconds: Time-to-live in seconds (default: 300)
    """
    with get_cache_connection() as conn:
        cursor = conn.cursor()

        current_time = time.time()
        expires_at = current_time + ttl_seconds

        data_json = json.dumps(data)

        # Insert or replace cached entry
        cursor.execute("""
            INSERT OR REPLACE INTO ticker_cache (ticker, data, cached_at, expires_at, hit_count)
            VALUES (?, ?, ?, ?, 0)
        """, (ticker, data_json, current_time, expires_at))

        conn.commit()

        # Log cache write
        structured_logger.logger.info(
            f"Cache WRITE for {ticker}",
            extra={
                "event_type": "cache_write",
                "ticker": ticker,
                "ttl_seconds": ttl_seconds,
                "expires_at": datetime.fromtimestamp(expires_at).isoformat(),
                "data_size_bytes": len(data_json),
                "severity": 6  # INFORMATIONAL
            }
        )


def invalidate_cached_ticker(ticker: str):
    """
    Manually invalidate a cached ticker entry.

    Args:
        ticker: Stock ticker symbol to invalidate
    """
    with get_cache_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("DELETE FROM ticker_cache WHERE ticker = ?", (ticker,))
        deleted = cursor.rowcount

        conn.commit()

        if deleted > 0:
            structured_logger.logger.info(
                f"Cache INVALIDATE for {ticker}",
                extra={
                    "event_type": "cache_invalidate",
                    "ticker": ticker,
                    "severity": 6  # INFORMATIONAL
                }
            )


def cleanup_expired_cache():
    """Remove expired cache entries (maintenance operation)"""
    with get_cache_connection() as conn:
        cursor = conn.cursor()

        current_time = time.time()

        cursor.execute("DELETE FROM ticker_cache WHERE expires_at < ?", (current_time,))
        deleted = cursor.rowcount

        conn.commit()

        if deleted > 0:
            structured_logger.logger.info(
                f"Cache cleanup: removed {deleted} expired entries",
                extra={
                    "event_type": "cache_cleanup",
                    "entries_removed": deleted,
                    "severity": 6  # INFORMATIONAL
                }
            )


# ============================================================================
# RATE LIMIT TRACKING
# ============================================================================

def record_api_call(session_id: str, ticker: str, tool_name: str):
    """
    Record an API call for rate limit tracking.

    Args:
        session_id: Unique session/correlation ID
        ticker: Ticker symbol being accessed
        tool_name: Name of the tool making the call
    """
    with get_cache_connection() as conn:
        cursor = conn.cursor()

        current_time = time.time()

        cursor.execute("""
            INSERT INTO rate_limits (session_id, timestamp, ticker, tool_name)
            VALUES (?, ?, ?, ?)
        """, (session_id, current_time, ticker, tool_name))

        conn.commit()


def check_rate_limit(session_id: str, tool_name: str) -> Tuple[bool, int, int]:
    """
    Check if session has exceeded rate limit.

    Args:
        session_id: Unique session/correlation ID
        tool_name: Name of the tool being called

    Returns:
        Tuple of (is_allowed, calls_in_window, retry_after_seconds)
        - is_allowed: True if under rate limit
        - calls_in_window: Number of calls in current window
        - retry_after_seconds: Seconds to wait before retry (0 if allowed)
    """
    with get_cache_connection() as conn:
        cursor = conn.cursor()

        current_time = time.time()
        window_start = current_time - RATE_LIMIT_WINDOW_SECONDS

        # Count calls in current window
        cursor.execute("""
            SELECT COUNT(*), MIN(timestamp)
            FROM rate_limits
            WHERE session_id = ?
            AND tool_name = ?
            AND timestamp > ?
        """, (session_id, tool_name, window_start))

        row = cursor.fetchone()
        calls_in_window = row[0] if row else 0
        oldest_call = row[1] if row and row[1] else current_time

        is_allowed = calls_in_window < RATE_LIMIT_MAX_CALLS

        # Calculate retry_after if rate limited
        if not is_allowed:
            # Time until oldest call in window expires
            retry_after = int(oldest_call + RATE_LIMIT_WINDOW_SECONDS - current_time) + 1
        else:
            retry_after = 0

        # Log rate limit check
        if not is_allowed:
            structured_logger.logger.warning(
                f"Rate limit EXCEEDED for session {session_id[:16]}...",
                extra={
                    "event_type": "rate_limit_exceeded",
                    "session_id": session_id,
                    "tool_name": tool_name,
                    "calls_in_window": calls_in_window,
                    "max_calls": RATE_LIMIT_MAX_CALLS,
                    "retry_after_seconds": retry_after,
                    "severity": 4,  # WARNING
                    "security_alert": True
                }
            )

        return is_allowed, calls_in_window, retry_after


def cleanup_old_rate_limits():
    """Remove rate limit records older than 1 hour (maintenance)"""
    with get_cache_connection() as conn:
        cursor = conn.cursor()

        cutoff_time = time.time() - 3600  # 1 hour ago

        cursor.execute("DELETE FROM rate_limits WHERE timestamp < ?", (cutoff_time,))
        deleted = cursor.rowcount

        conn.commit()

        if deleted > 0:
            structured_logger.logger.info(
                f"Rate limit cleanup: removed {deleted} old records",
                extra={
                    "event_type": "rate_limit_cleanup",
                    "records_removed": deleted,
                    "severity": 6  # INFORMATIONAL
                }
            )


# ============================================================================
# CACHE STATISTICS
# ============================================================================

def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics for monitoring.

    Returns:
        Dictionary with cache metrics
    """
    with get_cache_connection() as conn:
        cursor = conn.cursor()

        # Total cached entries
        cursor.execute("SELECT COUNT(*) FROM ticker_cache")
        total_entries = cursor.fetchone()[0]

        # Expired entries
        current_time = time.time()
        cursor.execute("SELECT COUNT(*) FROM ticker_cache WHERE expires_at < ?", (current_time,))
        expired_entries = cursor.fetchone()[0]

        # Total hit count
        cursor.execute("SELECT SUM(hit_count) FROM ticker_cache")
        total_hits = cursor.fetchone()[0] or 0

        # Most cached tickers
        cursor.execute("""
            SELECT ticker, hit_count, cached_at
            FROM ticker_cache
            WHERE expires_at > ?
            ORDER BY hit_count DESC
            LIMIT 10
        """, (current_time,))

        top_tickers = [
            {"ticker": row[0], "hit_count": row[1], "cached_at": row[2]}
            for row in cursor.fetchall()
        ]

        return {
            "total_entries": total_entries,
            "valid_entries": total_entries - expired_entries,
            "expired_entries": expired_entries,
            "total_cache_hits": total_hits,
            "top_cached_tickers": top_tickers,
            "cache_hit_rate": round(total_hits / max(total_entries, 1), 2)
        }


# ============================================================================
# INITIALIZATION
# ============================================================================

# Initialize database on module import
try:
    init_cache_db()
except Exception as e:
    structured_logger.logger.error(
        f"Failed to initialize cache database: {e}",
        extra={
            "event_type": "cache_initialization_error",
            "error": str(e),
            "severity": 3  # ERROR
        }
    )


if __name__ == "__main__":
    # Test cache operations
    print("Testing cache operations...")

    # Test cache write and read
    test_data = {"price": 150.0, "pe_ratio": 25.0}
    set_cached_ticker("AAPL", test_data)

    cached = get_cached_ticker("AAPL")
    print(f"Cached data: {cached}")

    # Test cache miss
    missed = get_cached_ticker("NOTCACHED")
    print(f"Cache miss: {missed}")

    # Test rate limiting
    session_id = "test-session-123"
    for i in range(35):
        is_allowed, calls, retry_after = check_rate_limit(session_id, "get_market_data")
        if not is_allowed:
            print(f"Rate limited after {calls} calls. Retry after {retry_after}s")
            break
        record_api_call(session_id, "TEST", "get_market_data")

    # Get stats
    stats = get_cache_stats()
    print(f"\nCache stats: {json.dumps(stats, indent=2)}")
