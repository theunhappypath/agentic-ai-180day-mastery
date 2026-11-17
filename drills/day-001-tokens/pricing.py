"""Rate table. One place, not scattered constants.

Prices change. `LAST_VERIFIED` is the honest expiry stamp on everything this
module returns — and Sonnet 5's introductory rate has an expiry date of its own,
which is the whole point of putting a date in here on Day 1.

Verified against https://claude.com/pricing#api
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

LAST_VERIFIED = date(2026, 8, 26)
SOURCE = "https://claude.com/pricing#api"

# Cache multipliers apply to the *input* rate.
CACHE_WRITE_5M = 1.25
CACHE_WRITE_1H = 2.00
CACHE_READ = 0.10


@dataclass(frozen=True)
class Intro:
    """A promotional rate with a hard expiry."""

    input_per_mtok: float
    output_per_mtok: float
    through: date


@dataclass(frozen=True)
class Rate:
    model_id: str
    display_name: str
    input_per_mtok: float
    output_per_mtok: float
    context_window: int
    intro: Intro | None = None

    def on(self, day: date) -> tuple[float, float]:
        """Input/output $ per 1M tokens in effect on `day`."""
        if self.intro is not None and day <= self.intro.through:
            return self.intro.input_per_mtok, self.intro.output_per_mtok
        return self.input_per_mtok, self.output_per_mtok

    def is_intro_on(self, day: date) -> bool:
        return self.intro is not None and day <= self.intro.through


RATES: dict[str, Rate] = {
    "claude-opus-5": Rate(
        model_id="claude-opus-5",
        display_name="Claude Opus 5",
        input_per_mtok=5.00,
        output_per_mtok=25.00,
        context_window=1_000_000,
    ),
    "claude-sonnet-5": Rate(
        model_id="claude-sonnet-5",
        display_name="Claude Sonnet 5",
        input_per_mtok=3.00,
        output_per_mtok=15.00,
        context_window=1_000_000,
        intro=Intro(
            input_per_mtok=2.00,
            output_per_mtok=10.00,
            through=date(2026, 8, 31),
        ),
    ),
    "claude-haiku-4-5": Rate(
        model_id="claude-haiku-4-5",
        display_name="Claude Haiku 4.5",
        input_per_mtok=1.00,
        output_per_mtok=5.00,
        context_window=200_000,
    ),
}


def rate(model_id: str) -> Rate:
    try:
        return RATES[model_id]
    except KeyError:
        known = ", ".join(sorted(RATES))
        raise KeyError(
            f"No rate for {model_id!r}. Known: {known}. "
            f"Add it to pricing.py and bump LAST_VERIFIED."
        ) from None


def cost_usd(
    model_id: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    on: date | None = None,
    cache_ttl: str = "5m",
) -> float:
    """Dollar cost of one call.

    `input_tokens` from the API is the *uncached remainder only* — the cache
    fields are billed separately at their own multipliers. Pass all four.
    """
    day = on or date.today()
    r = rate(model_id)
    in_rate, out_rate = r.on(day)
    write_mult = CACHE_WRITE_1H if cache_ttl == "1h" else CACHE_WRITE_5M

    total = (
        input_tokens * in_rate
        + cache_creation_input_tokens * in_rate * write_mult
        + cache_read_input_tokens * in_rate * CACHE_READ
        + output_tokens * out_rate
    )
    return total / 1_000_000


def expiring_soon(within_days: int = 30, on: date | None = None) -> list[str]:
    """Human-readable warnings for rates that are about to change under you."""
    day = on or date.today()
    out: list[str] = []
    for r in RATES.values():
        if r.intro is None:
            continue
        left = (r.intro.through - day).days
        if 0 <= left <= within_days:
            out.append(
                f"{r.display_name}: introductory ${r.intro.input_per_mtok:.2f}/"
                f"${r.intro.output_per_mtok:.2f} per 1M expires in {left} day(s) "
                f"({r.intro.through}) → ${r.input_per_mtok:.2f}/${r.output_per_mtok:.2f}"
            )
        elif left < 0:
            out.append(f"{r.display_name}: introductory rate expired {-left} day(s) ago.")
    return out


def stale_days(on: date | None = None) -> int:
    return ((on or date.today()) - LAST_VERIFIED).days


if __name__ == "__main__":
    today = date.today()
    print(f"pricing.py — last_verified {LAST_VERIFIED} ({stale_days()} days ago)")
    print(f"source: {SOURCE}\n")
    print(f"{'model':<20} {'in $/1M':>9} {'out $/1M':>9}  effective")
    for r in RATES.values():
        i, o = r.on(today)
        tag = "intro" if r.is_intro_on(today) else "list"
        print(f"{r.model_id:<20} {i:>9.2f} {o:>9.2f}  {tag}")
    for w in expiring_soon():
        print(f"\n!! {w}")
