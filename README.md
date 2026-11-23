# Agentic AI & AI System Design — a 180-Day Mastery Journey

[![ci](https://github.com/theunhappypath/agentic-ai-180day-mastery/actions/workflows/ci.yml/badge.svg)](https://github.com/theunhappypath/agentic-ai-180day-mastery/actions/workflows/ci.yml)

A day-by-day curriculum for an engineer who already ships production systems and now
wants **agentic AI as an engineering discipline**, not as prompting — and the capstone
built while working through it.

---

## Who this is calibrated for

10+ years building scalable platforms, with an agentic system already shipped (AI SDLC
orchestration, Tauri + Rust, human approval gates) and migrated onto self-hosted OSS
models on owned GPU infrastructure.

So this skips "what is an LLM" and goes straight at the part that experience identified
as the hard part:

> orchestration state, failure recovery, evaluation, cost and latency budgets, and
> knowing exactly where a human needs to stay in the loop.

Every phase converts one of those from intuition into something you can **measure,
defend in a design review, and reproduce on demand**.

---

## The operating parameters

| Parameter | Value |
|---|---|
| Daily budget | **2 hours** — ~40 min concept, ~80 min hands-on |
| Cadence | **6 days/week**, 1 rest day → 180 learning days ≈ 30 weeks |
| Primary stack | **Python** (agents, evals, serving) + **TypeScript/Next.js** (UI) |
| Models | **Hybrid** — Claude API for the capability ceiling, self-hosted vLLM for infra depth, Ollama/llama.cpp locally for offline drills |
| Structure | One growing capstone + daily drills |
| Output | **9 public write-ups**, one per phase |

### The weekly rhythm

| Day | Mode | What happens |
|---|---|---|
| 1–4 | **Learn** | New concept (~40 min) + focused drill (~80 min) |
| 5 | **Build** | Capstone increment — the week's learning lands in SENTINEL |
| 6 | **Consolidate** | Re-run evals, write notes, review two earlier weeks, log the week's cost/latency numbers |

---

## Phases

| Phase | Days | Theme | Roadmap |
|---|---|---|---|
| 0 | 1–12 | Foundations & mental models — the mechanics you debug with | [phase-00](docs/phase-00-foundations.md) |
| 1 | 13–36 | Agent primitives — tools, loops, MCP, HITL | [phase-01](docs/phase-01-agent-primitives.md) |
| 2 | 37–66 | Context, memory & retrieval | [phase-02](docs/phase-02-context-memory-retrieval.md) |
| 3 | 67–96 | Multi-agent orchestration & durable execution | [phase-03](docs/phase-03-orchestration.md) |
| 4 | 97–120 | Evaluation, observability & reliability | [phase-04](docs/phase-04-evaluation-reliability.md) |
| 5 | 121–144 | Serving, inference & cost engineering | [phase-05](docs/phase-05-serving-inference-cost.md) |
| 6 | 145–156 | Adaptation — fine-tuning, distillation, routing | [phase-06](docs/phase-06-adaptation.md) |
| 7 | 157–174 | AI system design & security | [phase-07](docs/phase-07-system-design-security.md) |
| 8 | 175–180 | Harden & ship | [phase-08](docs/phase-08-harden-and-ship.md) |

### Lessons written

Lessons are written one per day, on the day, from the fixed schema in
[docs/days/_TEMPLATE.md](docs/days/_TEMPLATE.md). CI fails if a lesson is missing from
this table.

| Day | Phase | Lesson | Mode | Drill | Notes |
|---|---|---|---|---|---|
| 1 | 0 | [Tokenization and the real unit of cost](docs/days/day-001-tokenization.md) | learn | `drills/day-001-tokens/` | `notes/day-001.md` |
| 2 | 0 | [Transformer inference: prefill, decode, and the KV cache](docs/days/day-002-inference.md) | learn | `drills/day-002-inference/` | `notes/day-002.md` |
| 3 | 0 | Sampling, determinism and reproducibility (full lesson to come; [roadmap](docs/phase-00-foundations.md)) | learn | `drills/day-003-sampling/` | — |
| 4 | 0 | Context windows and lost in the middle (full lesson to come; [roadmap](docs/phase-00-foundations.md)) | learn | `drills/day-004-context/` | — |
| 5 | 0 | Set up your AI lab: one settings file, one door for every model call, one log (full lesson to come; [roadmap](docs/phase-00-foundations.md)) | build | `drills/day-005-lab/` · `src/agentic_mastery/lab/` | — |

---

## The capstone: SENTINEL

An **agentic incident response platform**. It ingests logs, traces, metrics, deploy
history and source; forms root-cause hypotheses; runs diagnostic tools; proposes a fix;
and escalates to a human with evidence. Spec: [docs/capstone-sentinel.md](docs/capstone-sentinel.md) ·
code: [sentinel/](sentinel/README.md)

| Version | Phase | What it adds |
|---|---|---|
| v0.1 | 1 | Single agent, 6 diagnostic tools, MCP server, approval gate |
| v0.2 | 2 | Hybrid retrieval over logs/traces/code/runbooks + retrieval eval set |
| v0.3 | 3 | Supervisor + investigator/verifier/reporter on a durable, resumable workflow |
| v0.4 | 4 | 150-case replay eval suite, CI gate, OTel tracing, cost dashboard |
| v0.5 | 5 | Cascade routing across local / self-hosted / frontier, measured $/incident |
| v0.6 | 6 | Distilled small model on the high-volume triage hop |
| v0.7 | 7 | Threat model, least-privilege scoping, egress control, audit trail |
| v1.0 | 8 | Load-tested, chaos-tested, documented, shipped |

### Phase write-ups

| Phase | Write-up |
|---|---|
| 0 | The cost & latency arithmetic every LLM app needs |
| 1 | Build the agent loop before you pick a framework |
| 2 | Write the retrieval eval before you tune retrieval |
| 3 | When multi-agent is the wrong answer |
| 4 | Eval-driven agent development |
| 5 | On-prem vs API: the breakeven math |
| 6 | Distilling your agent's hot path |
| 7 | Threat modelling an agent with production access |
| 8 | SENTINEL: six months, one platform, the numbers |

---

## Repository layout

```
.
├── docs/                    # THE COURSE — read-only while learning
│   ├── setup.md             #   environment, done once before Day 1
│   ├── capstone-sentinel.md #   capstone spec
│   ├── phase-NN-*.md        #   roadmap: every day of a phase in compact form
│   └── days/                #   full lessons, one per day
│       ├── _TEMPLATE.md
│       └── day-NNN-<slug>.md
├── drills/                  # YOUR WORK — one folder per day's practical
│   └── day-NNN-<slug>/
├── notes/                   # YOUR WORK — measurement journal, notes/day-NNN.md
├── sentinel/                # YOUR WORK — the capstone (agent, retrieval, evals, serving, corpus, ui)
├── designs/                 # YOUR WORK — Phase 7 written system designs
├── src/agentic_mastery/     # code promoted out of drills once a second consumer needs it
├── tests/                   # repo-level checks, incl. curriculum integrity
├── costs.jsonl              # append-only log of every model call, from Day 1 (created on Day 1)
├── pyproject.toml / uv.lock # one environment for the whole repo
└── .github/workflows/ci.yml # lint, format, tests on every push
```

The line that matters: **`docs/` is the course; everything else is what you produce from
it.** A lesson's `produces:` frontmatter names the exact paths it expects you to create.

---

## Working in this repo

```bash
uv sync                      # create .venv with runtime + dev deps
cp .env.example .env         # then add ANTHROPIC_API_KEY
uv run pytest                # curriculum integrity + any drill tests
uv run ruff check . && uv run ruff format .
```

Run drills from the repo root so they use the shared environment:

```bash
uv run python drills/day-001-tokens/tokviz.py drills/day-001-tokens/samples/*
```

Each day ends with one commit: `day NNN: <what you measured>`.

---

## Ground rules

1. **Measure, don't vibe.** Every day ends with a *Proof of understanding* — usually a
   number. If you can't produce the number, the day isn't done.
2. **Build the eval before you tune the thing.** It appears in Phases 2, 4 and 5 because
   it is the single most violated rule in the field.
3. **Report honest results, including losses.** Day 95 A/Bs single-agent vs multi-agent;
   publish the result *even if multi-agent loses*.
4. **No framework until Day 34.** Hand-roll the agent loop first. You cannot evaluate a
   framework you have never had to replace.
5. **Missed a day? Don't double up.** Shift the plan by one day. The curriculum is a
   sequence, not a calendar.

---

## Getting started

1. [docs/setup.md](docs/setup.md) — environment and model access.
2. Skim [docs/capstone-sentinel.md](docs/capstone-sentinel.md).
3. Start [Day 1](docs/days/day-001-tokenization.md).
