#!/usr/bin/env python3
"""
Phase 8: Ragas-based Evaluation for Financial Intelligence MCP

Evaluates the MCP server using Ragas metrics adapted for financial data retrieval.

Usage:
    python evaluate_ragas.py --golden-set tests/golden_set.json
    python evaluate_ragas.py --compare-baseline results/baseline_2026-01-08.json
"""

import json
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import argparse
import os

# Import MCP tools
from mcp_tools import check_client_suitability_impl, get_market_data_impl


async def run_mcp_tool(test_case: Dict[str, Any]) -> str:
    """Execute MCP tool call and return response."""
    ticker = test_case["ticker"]
    expected_tool = test_case["expected_tool"]
    
    # Always check compliance first
    compliance_response = await check_client_suitability_impl(ticker)
    compliance_data = json.loads(compliance_response)
    
    # If approved, get market data
    if compliance_data.get("compliance_status") == "APPROVED":
        if expected_tool == "get_market_data":
            market_response = await get_market_data_impl(ticker)
            return market_response
    
    return compliance_response


def check_compliance_gate(test_case: Dict[str, Any], response: str) -> float:
    """Check if compliance gate worked correctly (1.0 = correct, 0.0 = failed)."""
    expected_compliance = test_case.get("expected_compliance")
    
    try:
        response_data = json.loads(response)
        actual_status = response_data.get("compliance_status", "")
        
        if expected_compliance == "DENIED":
            return 1.0 if "DENIED" in actual_status else 0.0
        elif expected_compliance == "APPROVED":
            return 1.0 if "APPROVED" in actual_status else 0.0
        
        return 0.5  # Ambiguous
    except:
        return 0.0


def check_data_completeness(test_case: Dict[str, Any], response: str) -> float:
    """Check percentage of required fields present."""
    required_fields = test_case.get("required_fields", [])
    
    if not required_fields:
        return 1.0
    
    try:
        response_data = json.loads(response)
        fields_present = 0
        
        for field in required_fields:
            if "." in field:
                section, key = field.split(".", 1)
                if section in response_data and key in response_data[section]:
                    if response_data[section][key] is not None:
                        fields_present += 1
            else:
                if field in response_data and response_data[field] is not None:
                    fields_present += 1
        
        return fields_present / len(required_fields)
    except:
        return 0.0


def check_silent_failure(response: str) -> float:
    """Detect silent failures (1.0 = no failure, 0.0 = silent failure)."""
    try:
        response_data = json.loads(response)
        
        # Explicit error is NOT a silent failure
        if response_data.get("error", False):
            return 1.0
        
        # Check for empty market data
        if "market_metrics" in response_data:
            metrics = response_data["market_metrics"]
            if all(v is None for v in metrics.values()):
                return 0.0  # Silent failure
        
        return 1.0
    except:
        return 0.5


async def evaluate_test_cases(golden_set_path: str):
    """Run evaluation on golden test set."""
    print("=" * 80)
    print("PHASE 8: RAGAS EVALUATION - Financial Intelligence MCP")
    print("=" * 80)
    print()
    
    # Load test cases
    with open(golden_set_path, 'r') as f:
        data = json.load(f)
    test_cases = data["test_cases"]
    
    print(f"Loaded {len(test_cases)} test cases\n")
    
    # Run MCP tools
    print("Running MCP tools on test cases...")
    responses = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"  [{i}/{len(test_cases)}] {test_case['id']}: {test_case['ticker']}")
        response = await run_mcp_tool(test_case)
        responses.append(response)
    print(f"✓ Collected {len(responses)} responses\n")
    
    # Calculate metrics
    print("Calculating metrics...")
    compliance_scores = []
    completeness_scores = []
    silent_failure_scores = []
    
    for test_case, response in zip(test_cases, responses):
        compliance_scores.append(check_compliance_gate(test_case, response))
        completeness_scores.append(check_data_completeness(test_case, response))
        silent_failure_scores.append(check_silent_failure(response))
    
    results = {
        "compliance_gate_accuracy": sum(compliance_scores) / len(compliance_scores),
        "data_completeness": sum(completeness_scores) / len(completeness_scores),
        "silent_failure_detection": sum(silent_failure_scores) / len(silent_failure_scores)
    }
    
    return results, len(test_cases)


async def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Financial Intelligence MCP Server with Ragas"
    )
    parser.add_argument(
        "--golden-set",
        default="tests/golden_set.json",
        help="Path to golden test set JSON"
    )
    parser.add_argument(
        "--output",
        default="results/evaluation_{timestamp}.json",
        help="Path to save evaluation results"
    )
    parser.add_argument(
        "--compare-baseline",
        help="Path to baseline results for regression testing"
    )
    
    args = parser.parse_args()
    
    # Run evaluation
    results, test_count = await evaluate_test_cases(args.golden_set)
    
    # Print results
    print("\n" + "=" * 80)
    print("EVALUATION RESULTS")
    print("=" * 80 + "\n")
    
    for metric_name, score in results.items():
        print(f"{metric_name}: {score:.3f}")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = args.output.replace("{timestamp}", timestamp)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump({
            "timestamp": timestamp,
            "golden_set": args.golden_set,
            "metrics": results,
            "test_cases": test_count
        }, f, indent=2)
    
    print(f"\n✓ Results saved to: {output_path}")
    
    # Regression testing
    if args.compare_baseline:
        print(f"\nComparing to baseline: {args.compare_baseline}")
        with open(args.compare_baseline, 'r') as f:
            baseline = json.load(f)
        
        print("\nREGRESSION ANALYSIS:")
        print("-" * 80)
        
        regression_detected = False
        for metric_name in results.keys():
            current_score = results[metric_name]
            baseline_score = baseline["metrics"].get(metric_name, 0.0)
            diff = current_score - baseline_score
            
            status = "✓" if diff >= -0.05 else "✗"
            print(f"{status} {metric_name}: {baseline_score:.3f} → {current_score:.3f} ({diff:+.3f})")
            
            if diff < -0.05:
                regression_detected = True
        
        if regression_detected:
            print("\n⚠️  REGRESSION DETECTED: Some metrics degraded > 5%")
            sys.exit(1)
        else:
            print("\n✓ No significant regression detected")
            sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
