"""Metacognition: deterministic capability/error tracking (M5 baseline)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .outcomes import SQLiteOutcomeStore


@dataclass(frozen=True, slots=True)
class CapabilityReport:
    capability: str
    total: int
    failures: int
    success_rate: float | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "total": self.total,
            "failures": self.failures,
            "success_rate": self.success_rate,
            "status": self.status,
        }


def capability_report(outcomes: SQLiteOutcomeStore, *, capability: str, kind: str | None = None) -> CapabilityReport:
    rows = outcomes.list_outcomes(kind=kind, limit=1000)
    # capability is a simple tag in details/capability
    selected = [r for r in rows if r.details.get("capability") == capability or r.kind == capability]
    total = len(selected)
    failures = sum(1 for r in selected if r.status in {"failed", "error"})
    successes = sum(1 for r in selected if r.status in {"passed", "ok", "executed"})
    rate = (successes / total) if total else None
    if total == 0:
        status = "unknown"
    elif failures == 0:
        status = "healthy"
    elif rate is not None and rate >= 0.7:
        status = "degraded"
    else:
        status = "unhealthy"
    return CapabilityReport(capability=capability, total=total, failures=failures, success_rate=rate, status=status)
