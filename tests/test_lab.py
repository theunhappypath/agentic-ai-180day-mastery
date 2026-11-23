"""Offline checks for the lab (Day 5). No Ollama, no API key, no network."""

import json
from pathlib import Path

import pytest

from agentic_mastery.lab import call, load_config
from agentic_mastery.lab import tokens as lab_tokens
from agentic_mastery.lab.call import check
from agentic_mastery.lab.cli import main
from agentic_mastery.lab.config import ConfigError, Settings
from agentic_mastery.lab.log import read
from agentic_mastery.lab.pricing import cost_usd
from agentic_mastery.lab.providers import Reply
from agentic_mastery.lab.report import percentile, summarise

ROOT = Path(__file__).resolve().parents[1]

CONFIG = """
[log]
path = "runs.jsonl"

[defaults]
provider = "ollama"
model = "fake:1b"
temperature = 0.0
seed = 7
num_ctx = 1024
max_tokens = 64
"""


@pytest.fixture
def config(tmp_path: Path):
    p = tmp_path / "lab.toml"
    p.write_text(CONFIG, encoding="utf-8")
    return load_config(p)


def fake_send(read: int, text: str = "ok", stop: str = "stop"):
    """A provider that 'reads' `read` tokens, and remembers the settings it was given."""
    seen = {}

    def send(settings, prompt, system, **_):
        seen["settings"] = settings
        return Reply(
            text=text, input_tokens=read, output_tokens=3, ttft_ms=12.4, latency_ms=50.6,
            stop_reason=stop, timings={"load_ms": 0, "prefill_ms": 5, "decode_ms": 40},
        )  # fmt: skip

    send.seen = seen
    return send


def test_repo_config_loads_and_pins_every_setting():
    c = load_config(ROOT / "lab.toml")
    assert c.defaults.provider == "ollama"
    assert c.defaults.num_ctx >= 4096, "the default window should hold a real document"
    assert c.defaults.temperature == 0
    assert c.log_path == ROOT / "costs.jsonl"


def test_bad_settings_are_rejected(tmp_path: Path):
    with pytest.raises(ConfigError):
        Settings(provider="openai")
    with pytest.raises(ConfigError):
        Settings().with_(num_ctx=10)
    with pytest.raises(ConfigError):
        Settings().with_(nmu_ctx=4096)  # a typo must not silently fall back to a default
    p = tmp_path / "lab.toml"
    p.write_text("[defaults]\nnum_ctxx = 4096\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(p)


def test_call_sends_the_configured_settings_and_logs_one_line(config):
    send = fake_send(read=20)
    res = call("hello there", config=config, send=send, day=5, tags={"t": "1"})
    assert send.seen["settings"].num_ctx == 1024
    assert send.seen["settings"].seed == 7
    assert res.text == "ok"
    assert res.warnings == []

    records, bad = read(config.log_path)
    assert bad == 0 and len(records) == 1
    r = records[0]
    for key in (
        "ts", "run_id", "provider", "model", "settings", "tokens_sent", "tokens_read",
        "input_tokens", "output_tokens", "cache_creation_input_tokens",
        "cache_read_input_tokens", "ttft_ms", "latency_ms", "cost_usd", "warnings", "git", "tags",
    ):  # fmt: skip
        assert key in r, key
    assert r["settings"]["temperature"] == 0
    assert r["cost_usd"] == 0.0
    assert r["ttft_ms"] == 12 and r["latency_ms"] == 51


def test_overrides_apply_to_one_call_only(config):
    send = fake_send(read=20)
    call("hi", config=config, send=send, num_ctx=4096)
    assert send.seen["settings"].num_ctx == 4096
    call("hi", config=config, send=send)
    assert send.seen["settings"].num_ctx == 1024


def test_the_log_is_append_only(config):
    for _ in range(3):
        call("hi", config=config, send=fake_send(read=20))
    records, _ = read(config.log_path)
    assert len(records) == 3
    assert len({r["run_id"] for r in records}) == 3


def test_truncation_is_caught(config, monkeypatch):
    """Day 4's silent cut: we sent 7,884 tokens, the model read 2,050."""
    monkeypatch.setattr(lab_tokens, "count", lambda text, model, mapping: (7884, True))
    res = call("long document", config=config, send=fake_send(read=2050), num_ctx=4096)
    codes = [w["code"] for w in res.warnings]
    assert codes == ["wont_fit", "truncated"]
    assert "read 2,050" in res.warnings[1]["message"]


def test_a_prompt_that_fits_raises_no_warning(config, monkeypatch):
    monkeypatch.setattr(lab_tokens, "count", lambda text, model, mapping: (7884, True))
    res = call("long document", config=config, send=fake_send(read=7913), num_ctx=16384)
    assert res.warnings == []


def test_estimated_counts_only_flag_a_clear_shortfall():
    common = dict(num_ctx=None, max_tokens=64, stop_reason="stop", cost=0.0, model="m")
    assert check(tokens_sent=1000, exact=False, tokens_read=900, **common) == []
    assert [w["code"] for w in check(tokens_sent=1000, exact=False, tokens_read=500, **common)] == [
        "truncated"
    ]


def test_cut_off_answers_and_missing_prices_are_flagged():
    w = check(
        tokens_sent=None, exact=False, tokens_read=10, num_ctx=None, max_tokens=64,
        stop_reason="max_tokens", cost=None, model="claude-new",
    )  # fmt: skip
    assert [x["code"] for x in w] == ["cut_off", "no_price"]


def test_prices():
    assert cost_usd("ollama", "anything", input_tokens=10**6, output_tokens=10**6) == 0.0
    assert cost_usd(
        "anthropic", "claude-haiku-4-5", input_tokens=1_000_000, output_tokens=1_000_000
    ) == pytest.approx(6.00)
    assert cost_usd("anthropic", "not-a-model", input_tokens=1, output_tokens=1) is None


def test_percentile_is_nearest_rank():
    v = [100, 200, 300, 400, 500, 600, 700, 800, 900, 30_000]
    assert percentile(v, 50) == 500
    assert percentile(v, 95) == 30_000  # one slow call out of ten is the p95
    assert percentile([], 50) is None


def test_report_groups_by_model(config):
    for model in ("fake:1b", "fake:1b", "fake:2b"):
        call("hi", config=config, send=fake_send(read=20), model=model)
    rows = {r["model"]: r for r in summarise(read(config.log_path)[0])}
    assert rows["fake:1b"]["calls"] == 2
    assert rows["fake:2b"]["tokens_read"] == 20


def test_a_broken_line_does_not_break_the_report(config):
    call("hi", config=config, send=fake_send(read=20))
    with config.log_path.open("a") as fh:
        fh.write('{"half a line\n')
    records, bad = read(config.log_path)
    assert len(records) == 1 and bad == 1


def test_cli_report_and_last(config, capsys):
    call("hi", config=config, send=fake_send(read=20))
    assert main(["--config", str(config.path), "report"]) == 0
    assert "1 calls" in capsys.readouterr().out
    assert main(["--config", str(config.path), "last"]) == 0
    assert json.loads(capsys.readouterr().out)["model"] == "fake:1b"
