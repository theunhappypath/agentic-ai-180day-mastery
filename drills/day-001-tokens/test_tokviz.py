"""Offline checks for the Day 1 drill. No network, no API key, no billed calls."""

import io
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from rich.console import Console

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pricing  # noqa: E402
import tokviz  # noqa: E402

# ------------------------------------------------------------------- pricing


def test_cost_bills_each_token_class_at_its_own_rate():
    # Opus 5: $5 in / $25 out per 1M; 5m cache write 1.25x, cache read 0.1x.
    cost = pricing.cost_usd(
        "claude-opus-5",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
        cache_read_input_tokens=1_000_000,
    )
    assert cost == pytest.approx(5 + 25 + 5 * 1.25 + 5 * 0.10)


def test_intro_rate_applies_through_its_last_day_only():
    sonnet = pricing.rate("claude-sonnet-5")
    assert sonnet.on(sonnet.intro.through) == (2.00, 10.00)
    assert sonnet.on(date(2026, 9, 1)) == (3.00, 15.00)


def test_unknown_model_names_the_known_ones():
    with pytest.raises(KeyError, match="claude-opus-5"):
        pricing.rate("claude-nonexistent")


# --------------------------------------------------------- UTF-8 boundaries


def test_boundary_inside_a_multibyte_character_is_detected():
    data = "aé".encode()  # a=1 byte, é=2 bytes
    assert tokviz.utf8_split_offsets(data, [2, 1]) == [2]  # cut between é's bytes
    assert tokviz.utf8_split_offsets(data, [1, 2]) == []  # cut before é


def test_char_at_byte_walks_back_to_the_character_start():
    data = "aé".encode()
    assert tokviz.char_at_byte(data, 2) == ("é", 1)


# ------------------------------------------------------------ Claude counter


class FakeMessages:
    """count_tokens that charges 1 token per character plus a 6-token envelope."""

    def count_tokens(self, model, messages):
        return SimpleNamespace(input_tokens=len(messages[0]["content"]) + 6)


def test_counter_subtracts_the_message_envelope():
    client = SimpleNamespace(messages=FakeMessages())
    counter = tokviz.ClaudeCounter(client, ["m"])
    assert counter.count("m", "hello") == 5
    assert counter.envelope == {"m": 6}


def test_raw_counter_keeps_the_envelope():
    client = SimpleNamespace(messages=FakeMessages())
    counter = tokviz.ClaudeCounter(client, ["m"], correct_envelope=False)
    assert counter.count("m", "hello") == 11


# ------------------------------------------------------------ visualization


def test_torn_character_is_printed_once(monkeypatch):
    console = Console(file=io.StringIO(), record=True, width=80)
    monkeypatch.setattr(tokviz, "console", console)

    def fake_tok(text, **_):
        # "é" is split across two tokens, so their spans overlap.
        return {"input_ids": [1, 2, 3, 4], "offset_mapping": [(0, 1), (1, 2), (1, 2), (2, 3)]}

    tokviz.viz_local("aéb", fake_tok, "t")
    out = console.export_text()
    assert "aéb" in out
    assert "aééb" not in out
    assert "1 character(s) spread across multiple tokens" in out


# -------------------------------------------------------------------- main


def test_missing_api_key_gives_a_hint_not_a_traceback(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    console = Console(file=io.StringIO(), record=True, width=200)
    monkeypatch.setattr(tokviz, "console", console)

    assert tokviz.main([str(HERE / "samples" / "prose.txt")]) == 2
    assert "ANTHROPIC_API_KEY is not set" in console.export_text()
