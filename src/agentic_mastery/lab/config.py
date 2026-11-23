"""Load `lab.toml`: the one place the lab's settings live."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

CONFIG_NAME = "lab.toml"
PROVIDERS = {"ollama", "anthropic"}


class ConfigError(ValueError):
    """lab.toml is missing or has a value the lab cannot use."""


@dataclass(frozen=True)
class Settings:
    """Everything that changes what a model answers. Saved with every call."""

    provider: str = "ollama"
    model: str = "qwen2.5:7b-instruct"
    temperature: float = 0.0
    seed: int | None = 42
    num_ctx: int = 8192
    max_tokens: int = 512

    def __post_init__(self) -> None:
        if self.provider not in PROVIDERS:
            raise ConfigError(f"provider must be one of {sorted(PROVIDERS)}, not {self.provider!r}")
        if not 0 <= self.temperature <= 2:
            raise ConfigError(f"temperature must be between 0 and 2, not {self.temperature}")
        if self.num_ctx < 256:
            raise ConfigError(f"num_ctx must be at least 256, not {self.num_ctx}")
        if self.max_tokens < 1:
            raise ConfigError(f"max_tokens must be at least 1, not {self.max_tokens}")

    def with_(self, **overrides) -> Settings:
        """A copy with the given settings changed. `None` means "keep the default"."""
        known = {f.name for f in fields(self)}
        unknown = set(overrides) - known
        if unknown:
            raise ConfigError(f"unknown setting(s): {sorted(unknown)}")
        return replace(self, **{k: v for k, v in overrides.items() if v is not None})

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass(frozen=True)
class Config:
    path: Path
    log_path: Path
    defaults: Settings
    ollama_url: str = "http://localhost:11434"
    keep_alive: str = "15m"
    tokenizers: dict[str, str] = field(default_factory=dict)

    @property
    def root(self) -> Path:
        return self.path.parent


def find_config(start: Path | None = None) -> Path:
    """`$LAB_CONFIG` if set, else the nearest lab.toml from `start` (default: cwd) upward."""
    env = os.environ.get("LAB_CONFIG")
    if env:
        p = Path(env).expanduser()
        if not p.is_file():
            raise ConfigError(f"LAB_CONFIG points at {p}, which does not exist")
        return p
    here = (start or Path.cwd()).resolve()
    for d in (here, *here.parents):
        if (d / CONFIG_NAME).is_file():
            return d / CONFIG_NAME
    raise ConfigError(f"no {CONFIG_NAME} in {here} or any folder above it")


def load_config(path: Path | None = None) -> Config:
    path = (path or find_config()).resolve()
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path.name}: {e}") from None

    allowed = {f.name for f in fields(Settings)}
    d = raw.get("defaults", {})
    unknown = set(d) - allowed
    if unknown:
        raise ConfigError(f"{path.name} [defaults]: unknown key(s) {sorted(unknown)}")
    log = Path(raw.get("log", {}).get("path", "costs.jsonl"))
    ollama = raw.get("ollama", {})
    return Config(
        path=path,
        log_path=log if log.is_absolute() else path.parent / log,
        defaults=Settings(**d),
        ollama_url=ollama.get("url", "http://localhost:11434").rstrip("/"),
        keep_alive=ollama.get("keep_alive", "15m"),
        tokenizers=dict(raw.get("tokenizers", {})),
    )
