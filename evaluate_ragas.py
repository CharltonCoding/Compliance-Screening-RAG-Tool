#!/usr/bin/env python3
"""
Phase 8: Ragas-based Evaluation for Financial Intelligence MCP

This script evaluates the MCP server using Ragas metrics adapted for
financial data retrieval and compliance gates.

Usage:
    python evaluate_ragas.py --golden-set tests/golden_set.json
    python evaluate_ragas.py --compare-baseline results/baseline_2026-01-07.json
"""

import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
)
from ragas.llms import LangchainLLMWrapper
from langchain_anthropic import ChatAnthropic

# Import MCP tools for testing
import sys
sys.path.append(str(Path(__file__).parent))
from server import check_client_suitability, get_market_data
from logging_config import structured_logger


# ============================================================================
# CUSTOM RAGAS METRICS FOR FINANCIAL MCP
# ============================================================================

from dataclasses import dataclass, field
from ragas.metrics.base import SingleTurnMetric, MetricType
from ragas.dataset_schema import SingleTurnSample
from ragas.callbacks import Callbacks
import typing as t


@dataclass
class ComplianceGateAccuracy(SingleTurnMetric):
    """
    Measures whether compliance gates correctly block restricted tickers.

    Returns:
        1.0: Compliance gate worked correctly (blocked restricted or allowed valid)
        0.0: Compliance gate failed (allowed restricted or blocked valid)
    """
    name: str = "compliance_gate_accuracy"

    _required_columns: t.Dict[MetricType, t.Set[str]] = field(
        default_factory=lambda: {
            MetricType.SINGLE_TURN: {"user_input", "response", "reference"}
        }
    )

    async def _single_turn_ascore(
        self,
        sample: SingleTurnSample,
        callbacks: Callbacks
    ) -> float:
        try:
            # Extract expected compliance from reference
            reference_data = json.loads(sample.reference)
            expected_compliance = reference_data.get("expected_compliance")

            # Parse response
            response_data = json.loads(sample.response)

            # Check if compliance status matches expectation
            if expected_compliance == "DENIED":
                # Should be blocked
                if "DENIED" in response_data.get("compliance_status", ""):
                    return 1.0  # Correct block
                else:
                    return 0.0  # Failed to block (CRITICAL)
            elif expected_compliance == "APPROVED":
                # Should be allowed
                if "APPROVED" in response_data.get("compliance_status", ""):
                    return 1.0  # Correct allow
                else:
                    return 0.0  # Incorrectly blocked

            return 0.5  # Ambiguous
        except Exception as e:
            print(f"ComplianceGateAccuracy error: {e}")
            return 0.0


@dataclass
class DataCompletenessMetric(SingleTurnMetric):
    """
    Measures whether all required financial fields were retrieved.

    Returns:
        0.0 - 1.0: Percentage of required fields present in response
    """
    name: str = "data_completeness"

    _required_columns: t.Dict[MetricType, t.Set[str]] = field(
        default_factory=lambda: {
            MetricType.SINGLE_TURN: {"response", "reference"}
        }
    )

    async def _single_turn_ascore(
        self,
        sample: SingleTurnSample,
        callbacks: Callbacks
    ) -> float:
        try:
            # Extract required fields from reference
            reference_data = json.loads(sample.reference)
            required_fields = reference_data.get("required_fields", [])

            if not required_fields:
                return 1.0  # No required fields

            # Parse response
            response_data = json.loads(sample.response)

            # Check for presence of each required field
            fields_present = 0
            for field in required_fields:
                # Check nested structure (e.g., market_metrics.current_price)
                if "." in field:
                    section, key = field.split(".", 1)
                    if section in response_data and key in response_data[section]:
                        if response_data[section][key] is not None:
                            fields_present += 1
                else:
                    if field in response_data and response_data[field] is not None:
                        fields_present += 1

            return fields_present / len(required_fields)
        except Exception as e:
            print(f"DataCompletenessMetric error: {e}")
            return 0.0


@dataclass
class SilentFailureDetector(SingleTurnMetric):
    """
    Detects silent failures (responses that look successful but contain no data).

    Returns:
        1.0: No silent failure detected
        0.0: Silent failure detected (response succeeded but has empty/invalid data)
    """
    name: str = "silent_failure_detection"

    _required_columns: t.Dict[MetricType, t.Set[str]] = field(
        default_factory=lambda: {
            MetricType.SINGLE_TURN: {"response"}
        }
    )

    async def _single_turn_ascore(
        self,
        sample: SingleTurnSample,
        callbacks: Callbacks
    ) -> float:
        try:
            response_data = json.loads(sample.response)

            # Check for error flags
            if response_data.get("error", False):
                return 1.0  # Explicit error is NOT a silent failure

            # If compliance was denied, that's explicit (not silent)
            if response_data.get("compliance_status") == "DENIED":
                return 1.0

            # Check for empty data structures
            if "market_metrics" in response_data:
                metrics = response_data["market_metrics"]
                # All values are None or empty
                if all(v is None for v in metrics.values()):
                    return 0.0  # Silent failure detected

            # Check for placeholder values
            suspicious_values = ["N/A", "UNKNOWN", "null", "undefined"]
            response_str = json.dumps(response_data).upper()
            for sus in suspicious_values:
                if sus.upper() in response_str:
                    return 0.5  # Partial failure

            return 1.0  # No silent failure
        except Exception as e:
            print(f"SilentFailureDetector error: {e}")
            return 0.5


# ============================================================================
# EVALUATION ENGINE
# ============================================================================

class FinancialMCPEvaluator:
    """
    Evaluates Financial Intelligence MCP Server using Ragas metrics.
    """

    def __init__(self, golden_set_path: str, anthropic_api_key: Optional[str] = None):
        self.golden_set_path = Path(golden_set_path)
        self.anthropic_api_key = anthropic_api_key

        # Initialize LLM for Ragas metrics (if API key provided)
        if anthropic_api_key:
            self.llm = ChatAnthropic(
                model="claude-sonnet-4-5-20250929",
                api_key=anthropic_api_key,
                temperature=0.0  # Deterministic for evaluation
            )

            # Wrap for Ragas
            self.ragas_llm = LangchainLLMWrapper(self.llm)

            # Initialize metrics (with LLM-based metrics)
            self.metrics = [
                faithfulness,  # Ragas built-in
                answer_relevancy,  # Ragas built-in
                ComplianceGateAccuracy(),  # Custom
                DataCompletenessMetric(),  # Custom
                SilentFailureDetector()  # Custom
            ]
        else:
            # Without API key, only run custom metrics
            self.ragas_llm = None
            self.metrics = [
                ComplianceGateAccuracy(),  # Custom
                DataCompletenessMetric(),  # Custom
                SilentFailureDetector()  # Custom
            ]

    def load_golden_set(self) -> List[Dict[str, Any]]:
        """Load golden test set from JSON"""
        with open(self.golden_set_path, 'r') as f:
            data = json.load(f)
        return data["test_cases"]

    async def run_mcp_tool(self, test_case: Dict[str, Any]) -> str:
        """
        Execute MCP tool call and return response.

        This replaces the retrieval step in traditional RAG.
        """
        ticker = test_case["ticker"]
        expected_tool = test_case["expected_tool"]

        try:
            # Step 1: Always check compliance first
            compliance_response = await check_client_suitability(ticker)
            compliance_data = json.loads(compliance_response)

            # Step 2: If approved, get market data (if requested)
            if compliance_data.get("compliance_status") == "APPROVED":
                if expected_tool == "get_market_data":
                    market_response = await get_market_data(ticker)
                    return market_response

            # Compliance denied or only compliance check requested
            return compliance_response

        except Exception as e:
            # Return error as JSON
            return json.dumps({
                "error": True,
                "error_code": "EXECUTION_ERROR",
                "message": f"Test execution failed: {str(e)}",
                "ticker": ticker
            })

    def convert_to_ragas_dataset(self, test_cases: List[Dict[str, Any]], responses: List[str]) -> Dataset:
        """
        Convert golden set + responses to Ragas dataset format.
        """
        data = {
            "user_input": [],
            "retrieved_contexts": [],
            "response": [],
            "reference": []
        }

        for test_case, response in zip(test_cases, responses):
            data["user_input"].append(test_case["user_input"])

            # retrieved_contexts = the yfinance data (simulated as context)
            # In traditional RAG, this would be vector DB results
            data["retrieved_contexts"].append([
                f"Ticker: {test_case['ticker']}, Tool: {test_case['expected_tool']}"
            ])

            data["response"].append(response)

            # reference = ground truth
            data["reference"].append(json.dumps(test_case))

        return Dataset.from_dict(data)

    async def evaluate(self) -> Dict[str, Any]:
        """
        Run full evaluation on golden set.
        """
        print("=" * 80)
        print("PHASE 8: RAGAS EVALUATION - Financial Intelligence MCP")
        print("=" * 80)
        print()

        # Load test cases
        print(f"Loading golden set from: {self.golden_set_path}")
        test_cases = self.load_golden_set()
        print(f"✓ Loaded {len(test_cases)} test cases\n")

        # Run MCP tools on each test case
        print("Running MCP tools on test cases...")
        responses = []
        for i, test_case in enumerate(test_cases, 1):
            print(f"  [{i}/{len(test_cases)}] {test_case['id']}: {test_case['ticker']}")
            response = await self.run_mcp_tool(test_case)
            responses.append(response)
        print(f"✓ Collected {len(responses)} responses\n")

        # Convert to Ragas dataset
        print("Converting to Ragas dataset format...")
        dataset = self.convert_to_ragas_dataset(test_cases, responses)
        print(f"✓ Created dataset with {len(dataset)} samples\n")

        # Run Ragas evaluation
        print("Running Ragas evaluation with metrics:")
        for metric in self.metrics:
            print(f"  - {metric.name}")
        print()

        results = evaluate(
            dataset,
            metrics=self.metrics,
            llm=self.ragas_llm
        )

        return results


# ============================================================================
# CLI INTERFACE
# ============================================================================

async def main():
    import argparse
    import os

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

    # Get Anthropic API key (optional for custom metrics only)
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        print("WARNING: ANTHROPIC_API_KEY environment variable not set")
        print("Only running custom metrics (compliance, completeness, silent failure)")
        print("Skipping LLM-based metrics (faithfulness, answer_relevancy)")
        print()

    # Run evaluation
    evaluator = FinancialMCPEvaluator(args.golden_set, anthropic_api_key)
    results = await evaluator.evaluate()

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
            "metrics": {k: float(v) for k, v in results.items()},
            "test_cases": len(evaluator.load_golden_set())
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
            current_score = float(results[metric_name])
            baseline_score = baseline["metrics"].get(metric_name, 0.0)
            diff = current_score - baseline_score

            status = "✓" if diff >= -0.05 else "✗"  # 5% tolerance
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
