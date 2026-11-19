"""Offline checks for the Day 2 drill. No Ollama, no network, no tokenizer download."""

import json
import sys
from pathlib import Path

import httpx
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import phases  # noqa: E402
import plot  # noqa: E402

# ------------------------------------------------------------------ prompts


class CharTokenizer:
    """One token per character, with a chat template shaped like Qwen's."""

    def encode(self, text, add_special_tokens=False):
        return [ord(c) for c in text]

    def decode(self, ids):
        return "".join(chr(i) for i in ids)

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        body = "".join(f"<{m['role']}>{m['content']}</>" for m in messages)
        return body + ("<assistant>" if add_generation_prompt else "")


class PairTokenizer(CharTokenizer):
    """Merges "ab" into one token, so cutting the filler can land between a and b."""

    def encode(self, text, add_special_tokens=False):
        out, i = [], 0
        while i < len(text):
            if text.startswith("ab", i):
                out.append(-1)
                i += 2
            else:
                out.append(ord(text[i]))
                i += 1
        return out

    def decode(self, ids):
        return "".join("ab" if i == -1 else chr(i) for i in ids)


@pytest.mark.parametrize("target", [300, 600, 1500])
def test_prompt_is_built_to_the_exact_token_count(target):
    tok = CharTokenizer()
    filler = phases.filler_ids(tok, "GET /health 200 3ms\n", target)
    text, n = phases.build_prompt(tok, target, filler, "c0ffee00")
    assert n == target == phases.count_tokens(tok, text)
    assert "c0ffee00" in text and phases.INSTRUCTION in text


def test_prompt_length_converges_when_tokens_merge_at_the_cut():
    tok = PairTokenizer()
    filler = phases.filler_ids(tok, "abxab yabz\n", 600)
    for target in range(200, 230):
        _, n = phases.build_prompt(tok, target, filler, "n")
        assert n == target


def test_nonce_comes_before_the_filler_so_runs_share_no_cache():
    tok = CharTokenizer()
    text = phases.render(tok, "deadbeef", "LOG")
    assert text.index("deadbeef") < text.index("LOG")


def test_prompt_shorter_than_its_scaffolding_is_refused():
    tok = CharTokenizer()
    with pytest.raises(ValueError, match="scaffolding"):
        phases.build_prompt(tok, 10, phases.filler_ids(tok, "x", 10), "n")


def test_filler_repeats_until_long_enough():
    assert len(phases.filler_ids(CharTokenizer(), "abc", 100)) >= 100


# ------------------------------------------------------------------ streaming


def ollama_stream(chunks: list[dict], now: list[float] | None = None) -> httpx.Client:
    """A fake Ollama that streams `chunks`, advancing `now[0]` by one second per chunk."""

    def body():
        for c in chunks:
            if now is not None:
                now[0] += 1
            yield (json.dumps(c) + "\n").encode()

    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=body()))
    return httpx.Client(base_url="http://ollama.test", transport=transport)


def test_ttft_is_the_first_chunk_with_text_not_the_first_chunk():
    now = [0.0]
    client = ollama_stream(
        [
            {"response": "", "done": False},
            {"response": "1", "done": False},
            {"response": "\n2", "done": False},
            {"response": "", "done": True, "prompt_eval_count": 1000, "eval_count": 2},
        ],
        now,
    )
    raw = phases.stream_once(client, "m", "p", 2, 4096, clock=lambda: now[0])
    assert raw["ttft_s"] == 2.0  # chunk 1 is empty; "1" arrives with chunk 2
    assert raw["total_s"] == 4.0
    assert raw["engine"]["prompt_eval_count"] == 1000


def test_ollama_error_line_is_raised():
    client = ollama_stream([{"error": "model requires more system memory"}])
    with pytest.raises(RuntimeError, match="more system memory"):
        phases.stream_once(client, "m", "p", 1, 4096)


def test_record_divides_by_measured_tokens_and_excludes_cached_from_prefill_rate():
    raw = {
        "ttft_s": 2.6,
        "total_s": 4.7,
        "engine": {
            "prompt_eval_count": 1000,
            "prompt_eval_cached_count": 4,
            "prompt_eval_duration": 2_490_000_000,
            "eval_count": 60,  # asked for 100, EOS came early
            "eval_duration": 1_200_000_000,
            "load_duration": 0,
            "done_reason": "stop",
        },
    }
    rec = phases.make_record(
        raw,
        session="S",
        model="m",
        model_bytes=4_700_000_000,
        num_ctx=4096,
        prompt_requested=1000,
        prompt_built=1000,
        output_requested=100,
        repeat=1,
        warmup=False,
        machine={},
    )
    assert rec["output_tokens_actual"] == 60
    assert rec["tpot_ms"] == 20.0  # 1200 ms / 60, not / 100
    assert rec["decode_tok_per_s"] == 50.0
    assert rec["prefill_tok_per_s"] == 400.0  # (1000 - 4) / 2.49 s
    assert rec["overhead_ms"] == 110.0  # 2600 wall - 2490 engine
    assert rec["decode_ms"] == 2100.0
    assert rec["tags"]["cell"] == "p1000-o100"


def test_matrix_that_overflows_num_ctx_is_rejected():
    with pytest.raises(SystemExit):
        phases.parse_args(["--prompts", "16000", "--outputs", "500", "--num-ctx", "8192"])


# ------------------------------------------------------------------ fits


def synthetic(session="S2", warm_noise=5000.0):
    """Runs from a known machine: TTFT = 15 ms + 2.5 ms/token, TPOT = 20 ms + 0.25 µs/token
    of prompt (the KV cache), so every number plot.py reports has a right answer."""
    rows = []
    for p in (100, 1000, 4000, 16000):
        for o in (10, 100, 500):
            for rep in range(3):
                tpot = 20 + 0.00025 * p
                ttft = 15 + 2.5 * p + (warm_noise if rep == 0 else 0)
                rows.append(
                    {
                        "session": session,
                        "model": "m",
                        "model_bytes": 5_000_000_000,
                        "machine": {"chip": "Apple M4 Pro"},
                        "warmup": rep == 0,
                        "prompt_tokens_requested": p,
                        "prompt_tokens_actual": p,
                        "output_tokens_requested": o,
                        "output_tokens_actual": o,
                        "ttft_ms": ttft,
                        "decode_ms": tpot * o,
                        "total_ms": ttft + tpot * o,
                        "overhead_ms": 15,
                        "tpot_ms": tpot,
                        "prefill_tok_per_s": 400.0,
                        "decode_tok_per_s": 1000 / tpot,
                        "tags": {"cell": f"p{p}-o{o}"},
                    }
                )
    return rows


def test_fit_line_recovers_slope_intercept_and_r2():
    f = plot.fit_line([0, 1, 2, 3], [5, 7, 9, 11])
    assert (f.intercept, f.slope, f.r2) == pytest.approx((5, 2, 1))


def test_summary_recovers_the_known_machine():
    s = plot.summarise(synthetic())
    assert s["runs"] == 24 and s["warmups"] == 12  # warm-ups never reach a fit
    assert s["ttft_fit"].slope == pytest.approx(2.5)
    assert s["ttft_fit"].intercept == pytest.approx(15)
    assert s["prefill_tok_s"] == pytest.approx(400)
    assert s["ttft_spread_pct"][16000] == pytest.approx(0)
    assert s["kv"]["pct"] == pytest.approx((24 / 20.025 - 1) * 100)
    assert s["kv"]["doubles_at"] == pytest.approx(100 + 20.025 / 0.00025)
    # 273 GB/s detected from the chip name, 5 GB model
    assert s["ceiling"]["tok_s"] == pytest.approx(54.6)
    assert s["workload_a"]["prompt"] == 16000 and s["workload_a"]["output"] == 10
    assert s["workload_b"]["prompt"] == 100 and s["workload_b"]["output"] == 500
    # Opus 5: $5 in, $25 out per million
    assert s["workload_a"]["usd"] == pytest.approx(16000 * 5e-6 + 10 * 25e-6)
    assert s["truncated"] == []


def test_latest_session_wins_unless_all_is_asked_for():
    rows = synthetic("01AAA") + synthetic("01BBB")
    assert {r["session"] for r in plot.select(rows)} == {"01BBB"}
    assert len(plot.select(rows, "all")) == len(rows)


def test_plots_are_written(tmp_path):
    rows = synthetic()
    paths = plot.draw(rows, plot.summarise(rows), tmp_path)
    assert [p.name for p in paths] == ["ttft-vs-prompt.png", "decode-vs-output.png"]
    assert all(p.stat().st_size > 10_000 for p in paths)
