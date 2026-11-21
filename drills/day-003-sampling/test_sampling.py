"""Offline checks for the Day 3 drill. No Ollama, no network."""

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import sampling  # noqa: E402


def test_summary_counts_and_orders():
    s = sampling.summary(["Brew Haven", "Brewscape", "Brew Haven", "Brew Haven"])
    assert s["distinct"] == 2
    assert list(s["counts"].items()) == [("Brew Haven", 3), ("Brewscape", 1)]


def test_odds_turns_logprobs_into_probabilities():
    response = {
        "response": "Canberra",
        "logprobs": [
            {
                "token": "Can",
                "top_logprobs": [
                    {"token": "Can", "logprob": math.log(0.9965)},
                    {"token": "CAN", "logprob": math.log(0.0032)},
                ],
            },
            {"token": "berra", "top_logprobs": [{"token": "berra", "logprob": 0.0}]},
        ],
    }
    o = sampling.odds(response)
    assert o["response"] == "Canberra"
    assert [s["chosen"] for s in o["steps"]] == ["Can", "berra"]
    assert o["steps"][0]["top"] == [("Can", 0.9965), ("CAN", 0.0032)]
    assert o["steps"][1]["top"] == [("berra", 1.0)]


def test_recorded_results_match_the_video():
    r = json.loads((HERE / "results-m4-pro.json").read_text(encoding="utf-8"))
    distinct = {t: s["distinct"] for t, s in r["coffee_by_temperature"].items()}
    assert distinct == {"0": 1, "0.7": 5, "1.0": 9, "1.5": 10}
    assert all(s["counts"] == {"Canberra": 20} for s in r["capital_by_temperature"].values())
    assert r["story_temp0_sequential"]["distinct"] == 1
    assert r["story_temp0_concurrent"]["distinct"] == 1
    assert r["story_temp1_seed42"]["distinct"] == 1
    assert r["story_temp1_noseed"]["distinct"] == 5
