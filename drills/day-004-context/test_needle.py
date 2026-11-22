"""Offline checks for the Day 4 drill. No Ollama, no network."""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import needle  # noqa: E402


def test_haystack_is_repeatable_and_has_no_hidden_facts():
    a = needle.haystack(8000, seed=1)
    assert a == needle.haystack(8000, seed=1)
    assert a != needle.haystack(8000, seed=2)
    assert len(a) == round(8000 / needle.TOKENS_PER_LINE)
    text = " ".join(a)
    assert "Wilhelmina" not in text
    assert "Grandma Rosa" not in text
    assert "locker code is" in text  # the look-alikes are there


def test_hide_puts_the_fact_at_the_right_depth():
    lines = [f"line {i}" for i in range(100)]
    assert needle.hide(lines, [(0.0, "FACT")])[0] == "FACT"
    assert needle.hide(lines, [(1.0, "FACT")])[-1] == "FACT"
    assert needle.hide(lines, [(0.5, "FACT")]).index("FACT") == 50
    assert lines == [f"line {i}" for i in range(100)]  # the original is untouched


def test_pie_document_hides_each_ingredient_once_in_order():
    lines, order = needle.pie_document(4000, trial=3)
    assert sorted(order) == sorted(needle.INGREDIENTS)
    facts = [line for line in lines if "Grandma Rosa" in line]
    assert facts == [needle.PIE_FACT.format(x) for x in order]
    positions = [lines.index(f) / len(lines) for f in facts]
    for pos, slot in zip(positions, needle.SLOTS, strict=True):
        assert abs(pos - slot) < 0.01


def test_split_keeps_every_line():
    lines = list(range(1001))
    parts = needle.split(lines, 4)
    assert len(parts) == 4
    assert [x for p in parts for x in p] == lines


def test_scoring():
    assert needle.found("The code is 7342.", "7342")
    assert not needle.found("There is no information about that person.", "7342")
    items = ["cinnamon", "black pepper", "figs"]
    assert needle.listed("Cinnamon, figs", items) == [True, False, True]
    assert needle.extras("cinnamon, nutmeg, Black Pepper.", items) == ["nutmeg"]


def test_recorded_results_match_the_video():
    r = json.loads((HERE / "results-m4-pro.json").read_text(encoding="utf-8"))
    d = r["default_window"]
    assert d["window"] == 4096
    assert [x["prompt_tokens"] for x in d["runs"]] == [2050, 2050, 2050]
    assert [x["found"] for x in d["runs"]] == [False, False, True]
    assert all(x["found"] for x in r["one_fact"]) and len(r["one_fact"]) == 44
    by_slot = {k: t["by_slot"] for k, t in r["ten_facts"].items()}
    assert {k: sum(v) for k, v in by_slot.items()} == {
        "4000": 47,
        "8000": 42,
        "16000": 35,
        "30000": 32,
    }
    assert by_slot["30000"] == [5, 1, 5, 3, 4, 1, 2, 2, 4, 5]
    assert sum(r["in_pieces"]["by_slot"]) == 48
