"""Read the log back: per model, how many calls, how many tokens, how slow, how much."""

from __future__ import annotations

import math
from collections import defaultdict


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile: the value at or below which p% of the values fall."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def matches(record: dict, filters: dict[str, str]) -> bool:
    tags = record.get("tags") or {}
    return all(str(tags.get(k)) == v for k, v in filters.items())


def summarise(records: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in records:
        groups[(r.get("provider", "?"), r.get("model", "?"))].append(r)
    rows = []
    for (provider, model), rs in sorted(groups.items()):
        lat = [r["latency_ms"] for r in rs if r.get("latency_ms") is not None]
        ttft = [r["ttft_ms"] for r in rs if r.get("ttft_ms") is not None]
        costs = [r.get("cost_usd") for r in rs]
        rows.append(
            {
                "provider": provider,
                "model": model,
                "calls": len(rs),
                "tokens_read": sum(r.get("tokens_read") or r.get("input_tokens", 0) for r in rs),
                "tokens_written": sum(r.get("output_tokens", 0) for r in rs),
                "ttft_p50_ms": percentile(ttft, 50),
                "latency_p50_ms": percentile(lat, 50),
                "latency_p95_ms": percentile(lat, 95),
                "latency_max_ms": max(lat) if lat else None,
                "cost_usd": sum(c for c in costs if c is not None),
                "unpriced_calls": sum(c is None for c in costs),
                "warnings": sum(len(r.get("warnings") or []) for r in rs),
            }
        )
    return rows


def warning_lines(records: list[dict]) -> list[tuple[dict, dict]]:
    return [(r, w) for r in records for w in (r.get("warnings") or [])]
