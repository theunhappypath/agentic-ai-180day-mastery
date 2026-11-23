"""Send one request to a model and time it. One function per provider, one shape out.

Both stream, so the time to the first token (Day 2) is measured by the clock, not guessed.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache

import httpx

from .config import Settings

Clock = Callable[[], float]


@dataclass
class Reply:
    text: str
    input_tokens: int  # uncached prompt tokens; + the two cache fields = everything it read
    output_tokens: int
    ttft_ms: float
    latency_ms: float
    stop_reason: str | None = None  # "length" / "max_tokens" = cut off by max_tokens
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    timings: dict = field(default_factory=dict)  # engine-reported phases, when available
    model_digest: str | None = None


class ProviderError(RuntimeError):
    pass


def messages_for(prompt: str, system: str | None) -> list[dict]:
    msgs = [{"role": "system", "content": system}] if system else []
    return [*msgs, {"role": "user", "content": prompt}]


# ------------------------------------------------------------------ ollama


@cache
def ollama_digest(url: str, model: str) -> str | None:
    """The exact model file Ollama has under this tag, so a rerun can check it's the same."""
    try:
        tags = httpx.get(f"{url}/api/tags", timeout=5).json().get("models", [])
    except httpx.HTTPError, ValueError:
        return None
    for m in tags:
        if model in (m.get("name"), m.get("model")):
            return (m.get("digest") or "")[:12] or None
    return None


def ollama(
    settings: Settings,
    prompt: str,
    system: str | None,
    *,
    url: str,
    keep_alive: str,
    clock: Clock = time.perf_counter,
) -> Reply:
    options = {
        "temperature": settings.temperature,
        "num_ctx": settings.num_ctx,
        "num_predict": settings.max_tokens,
    }
    if settings.seed is not None:
        options["seed"] = settings.seed
    payload = {
        "model": settings.model,
        "messages": messages_for(prompt, system),
        "stream": True,
        "keep_alive": keep_alive,
        "options": options,
    }
    parts: list[str] = []
    ttft = None
    final: dict = {}
    t0 = clock()
    try:
        with httpx.stream("POST", f"{url}/api/chat", json=payload, timeout=None) as resp:
            if resp.status_code != 200:
                resp.read()
                raise ProviderError(f"Ollama returned {resp.status_code}: {resp.text.strip()}")
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if "error" in chunk:
                    raise ProviderError(f"Ollama: {chunk['error']}")
                piece = chunk.get("message", {}).get("content", "")
                if piece:
                    if ttft is None:
                        ttft = clock() - t0
                    parts.append(piece)
                if chunk.get("done"):
                    final = chunk
    except httpx.ConnectError:
        msg = f"Ollama is not running at {url}. Start it with `ollama serve`."
        raise ProviderError(msg) from None
    total = clock() - t0
    ms = 1e-6  # Ollama durations are nanoseconds
    cached = final.get("prompt_eval_cached_count", 0) or 0
    return Reply(
        text="".join(parts),
        input_tokens=final.get("prompt_eval_count", 0) - cached,
        output_tokens=final.get("eval_count", 0),
        ttft_ms=(ttft if ttft is not None else total) * 1000,
        latency_ms=total * 1000,
        stop_reason=final.get("done_reason"),
        cache_read_input_tokens=cached,
        timings={
            "load_ms": round(final.get("load_duration", 0) * ms),
            "prefill_ms": round(final.get("prompt_eval_duration", 0) * ms),
            "decode_ms": round(final.get("eval_duration", 0) * ms),
        },
        model_digest=ollama_digest(url, settings.model),
    )


# --------------------------------------------------------------- anthropic


def anthropic(
    settings: Settings,
    prompt: str,
    system: str | None,
    *,
    clock: Clock = time.perf_counter,
    client=None,
    **_,
) -> Reply:
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ProviderError("ANTHROPIC_API_KEY is not set. Add it to .env (never commit it).")
        import anthropic as sdk

        client = sdk.Anthropic()
    kwargs = {
        "model": settings.model,
        "max_tokens": settings.max_tokens,
        "temperature": settings.temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    ttft = None
    t0 = clock()
    with client.messages.stream(**kwargs) as stream:
        for event in stream:
            if ttft is None and getattr(event, "type", None) == "content_block_delta":
                ttft = clock() - t0
        msg = stream.get_final_message()
    total = clock() - t0
    u = msg.usage
    return Reply(
        text="".join(b.text for b in msg.content if getattr(b, "type", None) == "text"),
        input_tokens=u.input_tokens or 0,
        output_tokens=u.output_tokens or 0,
        ttft_ms=(ttft if ttft is not None else total) * 1000,
        latency_ms=total * 1000,
        stop_reason=msg.stop_reason,
        cache_creation_input_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
        cache_read_input_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
    )


PROVIDERS = {"ollama": ollama, "anthropic": anthropic}
