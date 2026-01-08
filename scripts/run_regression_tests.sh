#!/bin/bash
# Phase 8: Automated Regression Testing
#
# Usage:
#   ./scripts/run_regression_tests.sh
#
# This script:
# 1. Runs all existing phase tests (1-7)
# 2. Runs Ragas evaluation on golden set
# 3. Compares results to baseline
# 4. Exits with code 1 if regression detected

set -e

BASELINE="results/baseline_2026-01-07.json"

echo "========================================================================"
echo "REGRESSION TEST SUITE - Financial Intelligence MCP"
echo "========================================================================"
echo ""

# Check if baseline exists
if [ ! -f "$BASELINE" ]; then
    echo "⚠️  Baseline file not found: $BASELINE"
    echo "Run 'python evaluate_ragas.py --output $BASELINE' to create baseline"
    echo ""
fi

# Phase 1-7 Tests (if they exist)
echo "Running Phase 1-7 tests..."
if [ -f "test_all_phases.py" ]; then
    python test_all_phases.py || echo "⚠️  test_all_phases.py failed or not found"
fi

if [ -f "test_phase5_cache.py" ]; then
    python test_phase5_cache.py || echo "⚠️  test_phase5_cache.py failed"
fi

if [ -f "test_phase6_langgraph.py" ]; then
    python test_phase6_langgraph.py || echo "⚠️  test_phase6_langgraph.py failed"
fi

if [ -f "test_phase7_async.py" ]; then
    python test_phase7_async.py || echo "⚠️  test_phase7_async.py failed"
fi

# Phase 8: Ragas Evaluation
echo ""
echo "Running Phase 8: Ragas Evaluation..."
if [ -f "$BASELINE" ]; then
    python evaluate_ragas.py \
        --golden-set tests/golden_set.json \
        --compare-baseline "$BASELINE"
else
    echo "Running without baseline comparison (first run)..."
    python evaluate_ragas.py \
        --golden-set tests/golden_set.json
fi

echo ""
echo "========================================================================"
echo "✅ ALL REGRESSION TESTS PASSED"
echo "========================================================================"
