# Capstone — SENTINEL

**An agentic incident response platform.**

Rename it whatever you like. What matters is the shape of the problem.

---

## The problem statement

A production service degrades. Something is wrong. Right now a human on-call engineer
opens six tabs — dashboards, logs, traces, the deploy pipeline, the repo, the runbook —
and spends 20 minutes building a mental model before they can even form a hypothesis.

SENTINEL does that first 20 minutes. It ingests the alert, gathers evidence across
heterogeneous sources, forms and tests root-cause hypotheses in parallel, and hands the
human a ranked set of hypotheses **with the evidence attached** and a proposed remediation
— stopping at an approval gate before it touches anything.

It is explicitly **not** an autonomous remediation system. The human stays in the loop at
every mutating action. That constraint is a feature: it is exactly the "where does a human
need to stay in the loop" question, made concrete.

---

## Why this capstone

It refuses to let you skip a single phase.

| It forces you to learn | Because |
|---|---|
| Heterogeneous retrieval | Logs, traces, metrics, code and runbooks need **four different indexes**, not one vector store |
| Hard latency budgets | Incident response is latency-critical. A 4-minute investigation is useless |
| Parallel orchestration | Five hypotheses must be tested concurrently, then merged and ranked |
| Durable execution | Investigations outlive processes. Kill it mid-run; it must resume |
| Replay-based evaluation | You have ground truth — the actual postmortem said what the cause was |
| Real security stakes | The agent has read access to production. That is a genuine threat model |
| Cost engineering | Alerts fire constantly. $/incident decides whether this could ever ship |

---

## The seeded incident corpus

Built in Phase 1 (Day 17), extended throughout. This is the single most important asset in
the project — everything downstream is evaluated against it.

Each incident case contains:

```
corpus/incidents/INC-0042/
├── alert.json           # the triggering alert
├── logs/                # log slices from the affected window, multiple services
├── traces/              # distributed traces, some with the smoking gun
├── metrics.json         # time series across the window
├── deploys.json         # what shipped in the preceding 24h
├── repo-ref.json        # commit SHAs and diffs in scope
├── runbook.md           # the runbook that may or may not cover this
└── ground-truth.json    # actual root cause, actual fix, and the minimal evidence set
```

Sources, in order of preference:

1. **Public postmortems.** Cloud providers, GitHub, Cloudflare and others publish detailed
   incident reports. Reconstruct synthetic telemetry consistent with the narrative.
2. **Synthetic generation.** Write a fault injector that produces a known failure (a slow
   dependency, a bad config push, a memory leak, a cache stampede, a thundering herd on
   retry) and capture real telemetry from a toy multi-service app.
3. **Your own history**, sanitised, if you can.

Target: **20 cases by end of Phase 1**, **150 by end of Phase 4**. Balance the classes —
if 80% of your corpus is "bad deploy," your agent learns to always blame the deploy.

`ground-truth.json` must include a **minimal evidence set**: the specific log lines, spans
and diffs that a correct investigation had to surface. That is what makes trajectory
evaluation (Day 100) possible, not just outcome evaluation.

---

## Architecture, built up phase by phase

```
                       ┌─────────────┐
   alert ─────────────▶│  Triage     │  cheap/local model; classify + scope
                       └──────┬──────┘  (distilled in Phase 6)
                              │
                       ┌──────▼──────────────────┐
                       │  Supervisor             │  budgets, routing, HITL gates
                       └──────┬──────────────────┘   (Phase 3)
                              │  fan-out
        ┌──────────┬──────────┼──────────┬──────────┐
        ▼          ▼          ▼          ▼          ▼
   Hypothesis  Hypothesis  Hypothesis  ...        ...   (Phase 3)
     agent       agent       agent
        │          │          │
        └──────────┴────┬─────┴─────────────────────┘
                        ▼
                  ┌───────────┐
                  │ Verifier  │  challenges each hypothesis against evidence
                  └─────┬─────┘  (Phase 3)
                        ▼
                  ┌───────────┐
                  │ Reporter  │  ranked hypotheses + evidence + proposed fix
                  └─────┬─────┘
                        ▼
                  ╔═══════════╗
                  ║ HUMAN GATE║  nothing mutates without this   (Phase 1)
                  ╚═══════════╝

   Cross-cutting:
     Retrieval layer  — log / trace / code / runbook indexes + service graph  (Phase 2)
     Memory           — episodic (past incidents), semantic (service knowledge) (Phase 2)
     Eval harness     — replay 150 cases, judge, trajectory scoring            (Phase 4)
     Tracing + cost   — OTel spans, $ per span, per-incident cost              (Phase 4)
     Model router     — local → self-hosted → frontier cascade                 (Phase 5)
     Policy layer     — least-privilege tool scoping, egress control, audit    (Phase 7)
```

---

## Success metrics — the numbers you're chasing

Track these in `notes/` from the first time each becomes measurable. Set your own targets
at Day 17 and revise honestly.

| Metric | Definition | Measurable from |
|---|---|---|
| **Root-cause accuracy@1** | Top hypothesis matches ground truth | Phase 4 |
| **Root-cause accuracy@3** | Ground truth in top 3 | Phase 4 |
| **Evidence recall** | Fraction of the minimal evidence set actually surfaced | Phase 4 |
| **Time to hypothesis (p50/p95)** | Alert → ranked hypotheses | Phase 3 |
| **Cost per incident** | Total $ across all model calls | Phase 4 |
| **False confidence rate** | Confidently wrong top hypothesis — the metric that matters most | Phase 4 |
| **Resumption correctness** | Kill-and-resume produces the identical result | Phase 3 |
| **Injection resistance** | Red-team cases that fail to breach tool scoping | Phase 7 |

**False confidence rate** deserves special attention. An incident tool that is wrong but
uncertain wastes a minute. An incident tool that is wrong but *confident* sends an
engineer down a 40-minute dead end during an outage. Optimising for it will teach you more
about calibration than any paper.

---

## Scope discipline

Six months is not long. Things this project deliberately does **not** do:

- Auto-remediate. Every mutation is human-approved. Full stop.
- Integrate with real production. Use the corpus and a toy multi-service app.
- Support multiple tenants for real (Phase 7 designs it; you implement a thin version).
- Look good. The UI is a debugging surface, not a product.

If you find yourself building a nicer UI instead of a better eval suite, you have drifted.
