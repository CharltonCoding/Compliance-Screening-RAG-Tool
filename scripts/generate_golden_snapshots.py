#!/usr/bin/env python3
"""
Generate Golden Dataset Snapshots for Phase 8 Ragas Evaluation

This script fetches real yfinance data for all test tickers and saves snapshots
to tests/golden_set_snapshots.json for reproducible, stable testing.

Usage:
    python scripts/generate_golden_snapshots.py
"""

import json
import asyncio
from datetime import datetime
from pathlib import Path
import yfinance as yf


# Test tickers for golden dataset (20 tickers)
TEST_TICKERS = {
    # Valid tickers (6)
    "valid": ["AAPL", "MSFT", "JPM", "GE", "XOM", "IBM"],

    # Restricted tickers (3) - will be denied by compliance
    "restricted": ["RESTRICTED", "SANCTION", "BLOCKED"],

    # Invalid tickers (3) - not real tickers
    "invalid": ["NOTAREALTICKER", "ZZZZ", "INVALID123"],

    # Watchlist tickers (2) - TSLA is on enhanced watchlist
    "watchlist": ["TSLA", "META"],

    # Edge cases (3)
    "edge": ["EURUSD=X", "SPY", "BRK-A"],

    # For rate limiting tests (3) - use valid tickers
    "rate_limit": ["GOOGL", "AMZN", "NFLX"]
}


async def fetch_ticker_snapshot(ticker: str) -> dict:
    """
    Fetch comprehensive yfinance data for a single ticker.

    Returns a snapshot dict with all available data or error info.
    """
    print(f"  Fetching: {ticker}...", end=" ")

    try:
        stock = yf.Ticker(ticker)

        # Run in thread pool since yfinance is blocking
        info = await asyncio.to_thread(lambda: stock.info)

        # Try to get ownership data
        institutional_holders = await asyncio.to_thread(lambda: stock.institutional_holders)
        major_holders = await asyncio.to_thread(lambda: stock.major_holders)

        # Check if data exists
        has_info = bool(info and len(info) > 0)
        has_institutional = institutional_holders is not None and not institutional_holders.empty
        has_major = major_holders is not None and not major_holders.empty

        snapshot = {
            "ticker": ticker,
            "fetched_at": datetime.now().isoformat(),
            "data_available": has_info,
            "info": info if has_info else {},
            "ownership": {
                "institutional_holders_available": has_institutional,
                "major_holders_available": has_major,
                "institutional_holders_count": len(institutional_holders) if has_institutional else 0,
                "major_holders_count": len(major_holders) if has_major else 0
            }
        }

        print(f"✓ (data={'yes' if has_info else 'no'}, ownership={'yes' if (has_institutional or has_major) else 'no'})")
        return snapshot

    except Exception as e:
        print(f"✗ Error: {str(e)[:50]}")
        return {
            "ticker": ticker,
            "fetched_at": datetime.now().isoformat(),
            "data_available": False,
            "error": str(e),
            "info": {},
            "ownership": {
                "institutional_holders_available": False,
                "major_holders_available": False,
                "institutional_holders_count": 0,
                "major_holders_count": 0
            }
        }


async def generate_snapshots():
    """Generate snapshots for all test tickers."""
    print("=" * 80)
    print("GENERATING GOLDEN DATASET SNAPSHOTS")
    print("=" * 80)
    print()

    all_snapshots = {}

    # Flatten all tickers
    all_tickers = []
    for category, tickers in TEST_TICKERS.items():
        all_tickers.extend(tickers)

    # Remove duplicates while preserving order
    all_tickers = list(dict.fromkeys(all_tickers))

    print(f"Fetching data for {len(all_tickers)} tickers...")
    print()

    # Fetch snapshots for each ticker
    for ticker in all_tickers:
        snapshot = await fetch_ticker_snapshot(ticker)
        all_snapshots[ticker] = snapshot

    # Save to file
    output_path = Path(__file__).parent.parent / "tests" / "golden_set_snapshots.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "ticker_count": len(all_snapshots),
            "snapshots": all_snapshots
        }, f, indent=2)

    print()
    print("=" * 80)
    print(f"✓ Snapshots saved to: {output_path}")
    print(f"✓ Total tickers: {len(all_snapshots)}")

    # Summary stats
    valid_count = sum(1 for s in all_snapshots.values() if s.get("data_available", False))
    ownership_count = sum(1 for s in all_snapshots.values()
                         if s.get("ownership", {}).get("institutional_holders_available", False) or
                            s.get("ownership", {}).get("major_holders_available", False))

    print(f"✓ Valid data: {valid_count}/{len(all_snapshots)}")
    print(f"✓ With ownership data: {ownership_count}/{len(all_snapshots)}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(generate_snapshots())
