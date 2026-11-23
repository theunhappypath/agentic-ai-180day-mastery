"""The lab notebook: an append-only JSONL file, one line per model call, never rewritten."""

from __future__ import annotations

import contextlib
import json
import platform
import secrets
import subprocess
import time
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def ulid() -> str:
    """A sortable, unique run id (same format as Day 1)."""
    v = (int(time.time() * 1000) << 80) | secrets.randbits(80)
    return "".join(_CROCKFORD[(v >> (5 * i)) & 31] for i in range(25, -1, -1))


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


SESSION = ulid()  # one per process: every call from one script run shares it


def append(record: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def read(path: Path) -> tuple[list[dict], int]:
    """(records, unreadable line count). A half-written last line never breaks a report."""
    if not path.exists():
        return [], 0
    records, bad = [], 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            bad += 1
    return records, bad


def _git(root: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=5, check=True
        )
    except OSError, subprocess.SubprocessError:
        return None
    return out.stdout.strip()


@cache
def git_state(root: Path) -> dict:
    """Which version of the code made this call, and whether it had uncommitted changes."""
    commit = _git(root, "rev-parse", "--short=12", "HEAD")
    status = _git(root, "status", "--porcelain", "--untracked-files=no")
    return {"commit": commit, "dirty": bool(status) if status is not None else None}


@cache
def machine() -> dict:
    chip = platform.processor() or platform.machine()
    if platform.system() == "Darwin":
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            chip = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            ).stdout.strip()
    return {"os": f"{platform.system()} {platform.release()}", "chip": chip}
