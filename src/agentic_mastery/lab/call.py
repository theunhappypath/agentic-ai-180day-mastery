"""`call()`: the one door every model call in this repo goes through.

Five steps, every time:
  1. settings  - read lab.toml, apply this call's overrides; nothing left to hidden defaults
  2. count     - tokens we are about to send (Day 1); warn now if they can't fit (Day 4)
  3. send      - stream the request; time the first token and the whole call (Day 2)
  4. check     - did the model read everything we sent? did the answer get cut off?
  5. record    - one line in the log: settings, tokens, timings, cost, warnings, git commit
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from . import log, pricing, tokens
from .config import Config, load_config
from .providers import PROVIDERS, Reply

TRUNCATION_ESTIMATE_SLACK = 0.75  # with an estimated count, only flag a clear shortfall


@dataclass
class Result:
    text: str
    record: dict

    @property
    def warnings(self) -> list[dict]:
        return self.record["warnings"]


def check(
    *,
    tokens_sent: int | None,
    exact: bool,
    tokens_read: int | None,
    num_ctx: int | None,
    max_tokens: int,
    stop_reason: str | None,
    cost: float | None,
    model: str,
) -> list[dict]:
    """The lab's guards. Pass `tokens_read=None` for the before-sending checks only."""
    out: list[dict] = []
    approx = "" if exact else "about "
    if tokens_read is None:
        if tokens_sent is not None and num_ctx and tokens_sent + max_tokens > num_ctx:
            out.append(
                {
                    "code": "wont_fit",
                    "message": f"The prompt is {approx}{tokens_sent:,} tokens, plus room for a "
                    f"{max_tokens:,}-token answer: more than the {num_ctx:,}-token window "
                    f"(num_ctx). The start of the prompt will be dropped.",
                }
            )
        return out

    if tokens_sent is not None:
        limit = tokens_sent if exact else tokens_sent * TRUNCATION_ESTIMATE_SLACK
        if tokens_read < limit:
            out.append(
                {
                    "code": "truncated",
                    "message": f"Sent {approx}{tokens_sent:,} tokens, but the model read "
                    f"{tokens_read:,}. The start of the prompt was dropped. Raise num_ctx.",
                }
            )
    if stop_reason in ("length", "max_tokens"):
        out.append(
            {
                "code": "cut_off",
                "message": f"The answer stopped at max_tokens ({max_tokens:,}). "
                f"It may be incomplete.",
            }
        )
    if cost is None:
        out.append(
            {
                "code": "no_price",
                "message": f"No price on file for {model}. Add it to lab/pricing.py.",
            }
        )
    return out


def call(
    prompt: str,
    *,
    system: str | None = None,
    config: Config | None = None,
    log_path: Path | None = None,
    write_log: bool = True,
    day: int | None = None,
    component: str = "drill",
    tags: dict | None = None,
    send=None,
    **overrides,
) -> Result:
    """Ask a model one question, measure it, and write it down.

    `overrides` change one setting for this call only (e.g. `num_ctx=16384`). `send`
    replaces the provider function; tests use it to run without a model.
    """
    # 1. settings
    config = config or load_config()
    load_dotenv(config.root / ".env", override=False)
    s = config.defaults.with_(**overrides)

    # 2. count, and warn before sending
    text = f"{system}\n\n{prompt}" if system else prompt
    if s.provider == "ollama":
        tokens_sent, exact = tokens.count(text, s.model, config.tokenizers)
    else:  # the API counts for us, and refuses an oversized prompt instead of trimming it
        tokens_sent, exact = None, False
    num_ctx = s.num_ctx if s.provider == "ollama" else None
    warnings = check(
        tokens_sent=tokens_sent,
        exact=exact,
        tokens_read=None,
        num_ctx=num_ctx,
        max_tokens=s.max_tokens,
        stop_reason=None,
        cost=0.0,
        model=s.model,
    )

    # 3. send
    send = send or PROVIDERS[s.provider]
    reply: Reply = send(s, prompt, system, url=config.ollama_url, keep_alive=config.keep_alive)

    # 4. check
    tokens_read = (
        reply.input_tokens + reply.cache_creation_input_tokens + reply.cache_read_input_tokens
    )
    cost = pricing.cost_usd(
        s.provider,
        s.model,
        input_tokens=reply.input_tokens,
        output_tokens=reply.output_tokens,
        cache_creation_input_tokens=reply.cache_creation_input_tokens,
        cache_read_input_tokens=reply.cache_read_input_tokens,
    )
    warnings += check(
        tokens_sent=tokens_sent,
        exact=exact,
        tokens_read=tokens_read,
        num_ctx=num_ctx,
        max_tokens=s.max_tokens,
        stop_reason=reply.stop_reason,
        cost=cost,
        model=s.model,
    )

    # 5. record
    record = {
        "ts": log.utc_now(),
        "run_id": log.ulid(),
        "session": log.SESSION,
        "day": day,
        "phase": 0,
        "component": component,
        "provider": s.provider,
        "model": s.model,
        "model_digest": reply.model_digest,
        "settings": s.as_dict(),
        "tokens_sent": tokens_sent,
        "tokens_sent_exact": exact,
        "tokens_read": tokens_read,
        "input_tokens": reply.input_tokens,
        "output_tokens": reply.output_tokens,
        "cache_creation_input_tokens": reply.cache_creation_input_tokens,
        "cache_read_input_tokens": reply.cache_read_input_tokens,
        "ttft_ms": round(reply.ttft_ms),
        "latency_ms": round(reply.latency_ms),
        **reply.timings,
        "stop_reason": reply.stop_reason,
        "cost_usd": cost,
        "prices_verified": pricing.LAST_VERIFIED.isoformat(),
        "prompt_sha256": hashlib.sha256(text.encode()).hexdigest()[:16],
        "prompt_chars": len(text),
        "warnings": warnings,
        "git": log.git_state(config.root),
        "machine": log.machine(),
        "tags": tags or {},
    }
    if write_log:
        log.append(record, log_path or config.log_path)
    return Result(text=reply.text, record=record)
