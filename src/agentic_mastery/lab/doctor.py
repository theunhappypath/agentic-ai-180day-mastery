"""`lab doctor`: is this machine ready to run experiments? One line per check."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

from . import log, pricing, tokens
from .config import Config

OK, WARN, FAIL = "ok", "warn", "fail"


@dataclass
class Check:
    name: str
    status: str
    detail: str


def _git_ignores(root, path: str) -> bool | None:
    try:
        r = subprocess.run(["git", "check-ignore", "-q", path], cwd=root, timeout=5)
    except OSError, subprocess.SubprocessError:
        return None
    return r.returncode == 0


def run(config: Config, client: httpx.Client | None = None) -> list[Check]:
    s = config.defaults
    out = [
        Check(
            "settings",
            OK,
            f"{config.path.name}: {s.provider} {s.model}, temperature {s.temperature:g}, "
            f"seed {s.seed}, num_ctx {s.num_ctx:,}, max_tokens {s.max_tokens:,}",
        )
    ]

    # secrets: the key may be missing (local-only is fine), but it must never be committed
    load_dotenv(config.root / ".env", override=False)
    ignored = _git_ignores(config.root, ".env")
    if ignored is False:
        out.append(Check("secrets", FAIL, ".env is NOT ignored by git. Add it to .gitignore."))
    else:
        key = "set" if os.environ.get("ANTHROPIC_API_KEY") else "not set (cloud calls off)"
        out.append(Check("secrets", OK, f".env ignored by git · ANTHROPIC_API_KEY {key}"))

    # ollama + model
    client = client or httpx.Client(base_url=config.ollama_url, timeout=5)
    try:
        version = client.get("/api/version").json().get("version", "?")
        models = client.get("/api/tags").json().get("models", [])
    except httpx.HTTPError, ValueError:
        out.append(Check("ollama", FAIL, f"not reachable at {config.ollama_url}: `ollama serve`"))
        models = None
    else:
        out.append(Check("ollama", OK, f"running at {config.ollama_url} · version {version}"))

    if s.provider == "ollama" and models is not None:
        found = next((m for m in models if s.model in (m.get("name"), m.get("model"))), None)
        if found is None:
            out.append(Check("model", FAIL, f"{s.model} not downloaded: `ollama pull {s.model}`"))
        else:
            size = found.get("size", 0) / 1e9
            out.append(
                Check("model", OK, f"{s.model} · {size:.1f} GB · digest {found['digest'][:12]}")
            )
            out.append(_window_check(client, s.model, s.num_ctx))

    # tokenizer: exact token counts make the truncation guard exact
    if s.provider == "ollama":
        if tokens.tokenizer_for(s.model, config.tokenizers) is not None:
            out.append(Check("tokens", OK, f"exact counts for {s.model} (its own tokenizer)"))
        else:
            out.append(
                Check(
                    "tokens",
                    WARN,
                    f"no tokenizer for {s.model}: counts are estimates (add it to [tokenizers])",
                )
            )

    age = pricing.days_since_verified()
    status = WARN if age > pricing.STALE_AFTER_DAYS else OK
    out.append(Check("prices", status, f"last checked {pricing.LAST_VERIFIED} ({age} days ago)"))

    records, bad = log.read(config.log_path)
    rel = (
        config.log_path.relative_to(config.root)
        if config.log_path.is_relative_to(config.root)
        else config.log_path
    )
    extra = f" · {bad} unreadable" if bad else ""
    out.append(Check("log", WARN if bad else OK, f"{rel} · {len(records):,} calls so far{extra}"))

    g = log.git_state(config.root)
    if g["commit"] is None:
        out.append(Check("git", WARN, "not a git repository: results can't name their code"))
    else:
        state = "uncommitted changes" if g["dirty"] else "clean"
        out.append(Check("git", WARN if g["dirty"] else OK, f"commit {g['commit']} · {state}"))
    return out


def _window_check(client: httpx.Client, model: str, num_ctx: int) -> Check:
    try:
        info = client.post("/api/show", json={"model": model}).json().get("model_info", {})
    except httpx.HTTPError, ValueError:
        return Check("window", WARN, "couldn't read the model's maximum window")
    max_ctx = next((v for k, v in info.items() if k.endswith(".context_length")), None)
    if max_ctx is None:
        return Check("window", WARN, f"num_ctx {num_ctx:,} · model maximum unknown")
    if num_ctx > max_ctx:
        return Check("window", FAIL, f"num_ctx {num_ctx:,} > this model's maximum {max_ctx:,}")
    return Check("window", OK, f"num_ctx {num_ctx:,} of this model's maximum {max_ctx:,}")
