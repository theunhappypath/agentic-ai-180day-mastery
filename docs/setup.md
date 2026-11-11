# Setup — do this before Day 1

Target: ~90 minutes. Everything below gets used from Day 1 onward, so don't defer it.

---

## 1. Python environment

Use `uv` — it is fast enough that you will actually create throwaway environments for
drills instead of polluting one big env.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

The repo layout already exists — see [Repository layout](../README.md#repository-layout).
`docs/` is the course; `drills/`, `notes/`, `sentinel/` and `designs/` are where your work goes.

Baseline Python deps are declared in `pyproject.toml`; lessons add more with `uv add` as
they need them. Create the environment and your secrets file:

```bash
uv sync
cp .env.example .env
```

---

## 2. Model access — all three tiers

You need all three because the whole journey is about the tradeoffs *between* them.

**Tier 1 — Frontier API (capability ceiling).** Get an Anthropic API key and put it in
`.env` as `ANTHROPIC_API_KEY`. Never commit it. Add `.env` to `.gitignore` on day zero.

**Tier 2 — Local laptop models (offline drills, zero marginal cost).** Install Ollama and
pull two models of different sizes so you can feel the quality/latency cliff:

```bash
ollama pull llama3.1:8b && ollama pull qwen2.5:3b
```

Also install `llama.cpp` from source at some point in Phase 5 — you'll want to read the
KV-cache code, not just use it.

**Tier 3 — Self-hosted GPU serving (Phase 5 onward).** Confirm now that you have SSH
access to your GPU box, know its VRAM, and can run `nvidia-smi`. Write the GPU model and
VRAM into `notes/day-000-setup.md` — Phase 5 asks you to compute breakeven economics from
those exact numbers.

---

## 3. Observability

You will be blind without this from Phase 4 onward, but wire the minimum now:

- **OpenTelemetry SDK** for Python — spans around every model call.
- A local trace viewer. Jaeger in Docker is enough to start; swap for a hosted LLM-native
  tool later if you prefer.
- A `costs.jsonl` append-only log: one line per model call with model, input tokens,
  output tokens, latency, and computed cost. **Start this on Day 1.** By Day 180 it is
  the most valuable artifact you own.

---

## 4. TypeScript side (needed from Phase 1, Day 35)

```bash
cd sentinel/ui && npx create-next-app@latest . --typescript --app
```

The UI stays deliberately thin — it exists so you can watch an agent think, approve a
gate, and read a trace. It is not the point of the exercise.

---

## 5. Version control

```bash
git add -A && git commit -m "day 000: environment + baselines"
```

Commit **every day**, even on consolidate days. The commit log becomes proof of the
180-day streak and the raw material for your phase write-ups.

---

## 6. The measurement journal

Create `notes/day-000-setup.md` with:

- Your GPU model and VRAM
- Your laptop's RAM and chip
- Baseline: time and cost of one `claude` API call with a 500-token prompt
- Baseline: time of the same prompt against `llama3.1:8b` locally

You will re-measure these at Day 180 and the delta will surprise you.

---

## A note on references

Every day cites sources **by name** — paper titles, official documentation, repository
names — rather than URLs. URLs rot; a paper title is searchable forever. When a day says
*Reference: "Lost in the Middle: How Language Models Use Long Contexts"*, search for it.
