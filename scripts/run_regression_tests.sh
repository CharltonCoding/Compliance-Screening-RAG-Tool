#!/bin/bash
# Phase 8: Automated Regression Testing
#
# Usage:
#   ./scripts/run_regression_tests.sh
#
# This script:
# 1. Runs Ragas evaluation on golden set
# 2. Compares results to baseline
# 3. Exits with code 1 if regression detected (>5% degradation)

set -e

BASELINE="results/baseline_2026-01-08.json"

echo "========================================================================"
echo "REGRESSION TEST SUITE - Financial Intelligence MCP"
echo "========================================================================"
echo ""

# Phase 8: Ragas Evaluation with Regression Check
echo "Running Phase 8: Ragas Evaluation..."
echo ""

python evaluate_ragas.py \
    --golden-set tests/golden_set.json \
    --compare-baseline "$BASELINE"

echo ""
echo "========================================================================"
echo "✅ ALL REGRESSION TESTS PASSED"
echo "========================================================================"
