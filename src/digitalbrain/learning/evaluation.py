"""Deterministic evaluation gate for promotion decisions (M5/M6 bridge).

Produces evidence; does not promote, deploy, or modify code/policy.
"""
from __future__ import annotations

from typing import Any

from digitalbrain.learning.outcomes import SQLiteOutcomeStore


def evaluate_promotion_gate(
    store: SQLiteOutcomeStore,
    *,
    kind: str,
    baseline_ref: str,
    candidate_ref: str,
    min_samples: int = 1,
    max_regression_drop: float = 0.2,
) -> dict[str, Any]:
    comparison = store.compare_baseline_candidate(
        kind=kind, baseline_ref=baseline_ref, candidate_ref=candidate_ref, min_samples=min_samples
    )
    regression = store.detect_regressions(kind=kind, window=20, min_samples=5, drop_threshold=max_regression_drop)
    reasons: list[str] = []
    passed = True
    if not comparison.get("enough_samples"):
        passed = False
        reasons.append("insufficient_comparison_samples")
    if comparison.get("recommendation") == "baseline_better":
        passed = False
        reasons.append("candidate_worse_than_baseline")
    if comparison.get("recommendation") == "insufficient_data":
        passed = False
        reasons.append("comparison_insufficient_data")
    if regression.get("regressed"):
        passed = False
        reasons.append("regression_detected")
    return {
        "passed": passed,
        "reasons": reasons,
        "comparison": comparison,
        "regression": regression,
        "policy": {
            "kind": kind,
            "baseline_ref": baseline_ref,
            "candidate_ref": candidate_ref,
            "min_samples": min_samples,
            "max_regression_drop": max_regression_drop,
        },
    }
