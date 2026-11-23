"""What a call costs. Promoted from Day 1's `drills/day-001-tokens/pricing.py`.

Prices change. `LAST_VERIFIED` is the expiry stamp on every number this module returns;
`lab doctor` warns when it is more than 30 days old. Local models cost $0 per token: their
real cost is your hardware and your time, which the latency columns measure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

LAST_VERIFIED = date(2026, 8, 26)
SOURCE = "https://claude.com/pricing#api"
STALE_AFTER_DAYS = 30

CACHE_WRITE_5M = 1.25  # multipliers on the input rate
CACHE_READ = 0.10


@dataclass(frozen=True)
class Rate:
    input_per_mtok: float
    output_per_mtok: float


# $ per 1M tokens, list prices as of LAST_VERIFIED. Add a model here before calling it.
RATES: dict[str, Rate] = {
    "claude-opus-5": Rate(5.00, 25.00),
    "claude-sonnet-5": Rate(3.00, 15.00),
    "claude-haiku-4-5": Rate(1.00, 5.00),
}


def cost_usd(
    provider: str,
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
) -> float | None:
    """Dollar cost of one call. `None` means "no price on file": the lab warns, never guesses."""
    if provider == "ollama":
        return 0.0
    r = RATES.get(model)
    if r is None:
        return None
    total = (
        input_tokens * r.input_per_mtok
        + cache_creation_input_tokens * r.input_per_mtok * CACHE_WRITE_5M
        + cache_read_input_tokens * r.input_per_mtok * CACHE_READ
        + output_tokens * r.output_per_mtok
    )
    return total / 1_000_000


def days_since_verified(today: date | None = None) -> int:
    return ((today or date.today()) - LAST_VERIFIED).days
