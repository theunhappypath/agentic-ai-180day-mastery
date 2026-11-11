# Phase 8 — Harden & Ship
**Days 175–180 · 1 week**

Six days to turn v0.7 into something you would actually put in front of people, and to
close the loop on 180 days of measurement.

The temptation this week is to add one more feature. Don't. The work is hardening,
documenting, and telling the truth about what you built.

**Phase deliverable:** *SENTINEL: six months, one platform, the numbers.*
**Capstone milestone:** SENTINEL v1.0.

---

### Day 175 — Load testing an agent system
**Concept (40 min)** — Load testing agents differs from load testing web services in three
ways: requests are long-lived (minutes, not milliseconds), expensive (a load test costs real
money, so you cannot casually 10× it), and stateful (concurrent investigations contend for
GPU, rate limits and approval queues). What you are looking for is the point where quality —
not just latency — starts degrading under load, because agents under budget pressure produce
worse answers rather than slower ones.

**Practical (80 min)** — Build a load test that replays real incident traffic at increasing
rates. Measure at each level: p50/p95/p99 time to hypothesis, root-cause accuracy, cost per
incident, error rate, and approval queue depth. Push until something breaks.

**Proof of understanding** — Report your maximum sustainable incident rate — defined by
quality holding, not by the system staying up. Then state what broke first. It is often the
human approval queue, which is a genuinely interesting finding about where the real
bottleneck in human-in-the-loop systems lives.

**Reference** — Your Day 133 queueing model — check whether it predicted this.

---

### Day 176 — Chaos testing at the system level
**Concept (40 min)** — You have tested individual failures since Phase 3. Now test
combinations, which is where real outages live: the model provider degrades *while* the
approval queue is backed up; retrieval fails *during* a fan-out; a checkpoint write fails
mid-resume. Combined failures interact in ways single-fault testing never surfaces.

**Practical (80 min)** — Build a chaos harness that injects randomized combinations of
failures during load: provider latency spikes, rate limit exhaustion, retrieval unavailability,
tool timeouts, process kills, and disk pressure on the checkpoint store. Run 100 randomized
scenarios and record every distinct failure mode.

**Proof of understanding** — Report how many of the 100 produced a *correct degraded result*
versus an incorrect result versus a hard failure. The middle category is the dangerous one —
a system that produces wrong answers under stress without signalling it is worse than one that
fails loudly. Fix every case you find there.

**Reference** — Your Day 118 fallback chains; Day 93 degradation ladder.

---

### Day 177 — Cost regression and the final economics
**Concept (40 min)** — Close the economic loop. You have `costs.jsonl` going back to Day 1 —
six months of every model call your system has ever made. Very few people have this, and it
is the raw material for the most credible thing you can publish.

**Practical (80 min)** — Produce the full cost history: cost per incident by version tag from
v0.1 to v1.0, with the change that caused each movement annotated. Compute total spend across
the 180 days, broken down by learning drills versus capstone versus evaluation runs. Then
recompute the Day 141 on-prem breakeven with six months of real utilisation data.

**Proof of understanding** — State cost per incident at v0.1 and at v1.0, and the accuracy at
each. A cost reduction alongside an accuracy improvement is the headline; if you traded one
for the other, say which and defend the trade.

**Reference** — `costs.jsonl`; `sentinel/CHANGELOG.md`.

---

### Day 178 — Documentation and architecture decision records
**Concept (40 min)** — Six months of decisions, most of which you will not remember the
reasoning for. ADRs capture the context, the decision, the alternatives considered, and the
consequences — and the ones worth writing are the decisions where you *changed your mind*,
because those encode the most information.

**Practical (80 min)** — Write ADRs for the ten most consequential decisions: the multi-agent
boundaries (Day 67), the framework decision (Day 34), hybrid over pure-dense retrieval (Day
46), event sourcing (Day 74), the cascade escalation signal (Day 135), the fine-tuning target
(Day 145), the permission model (Day 170), and three more of your choosing. Then write
`sentinel/README.md` — what it is, how to run it, and what its measured performance is.

**Proof of understanding** — At least three ADRs record a decision you reversed, with the
measurement that changed your mind. A design history with no reversals is a design history
that was not written honestly.

**Reference** — Your `notes/` across all 180 days.

---

### Day 179 — **[BUILD]** SENTINEL v1.0
**Concept (40 min)** — Ship it. v1.0 means: every chaos scenario handled, documentation
complete, evaluation suite green, cost within budget, security controls verified, and a
README someone else could follow.

**Practical (80 min)** — Final integration pass. Fix everything the chaos test surfaced. Run
the complete evaluation suite one last time. Run the red-team corpus. Tag `v1.0`. Write the
final changelog entry with all eight success metrics.

**Proof of understanding** — v1.0 against the targets you set on Day 5, before you knew
anything. Report every metric against its original target. Some you beat, some you missed, and
some targets turn out to have been the wrong thing to measure — which is itself the most
interesting finding, and worth saying out loud.

**Reference** — `sentinel/SPEC.md`, written 175 days ago.

---

### Day 180 — **[CONSOLIDATE]** Retro, publish, and what comes next
**Concept (40 min)** — Close the loop properly. Six months ago the goal was to convert
"orchestration state, failure recovery, evaluation, cost and latency budgets, and knowing
where a human stays in the loop" from intuition into engineering. Assess honestly whether that
happened, and where it did not.

**Practical (80 min)** — Three pieces of work:

1. **The retro.** Write `notes/RETRO.md`: what you believed on Day 1 that turned out to be
   wrong; the three highest-value days; the three lowest-value days; where the plan was
   miscalibrated; and what you would tell someone starting this tomorrow.

2. **The write-up.** Draft deliverable #9: **"SENTINEL: six months, one platform, the
   numbers."** This one is different from the other eight — it is the whole arc. Lead with the
   v0.1-to-v1.0 metric table. Include the cost history, the honest single-agent versus
   multi-agent result, the fine-tuning payback, the red-team numbers, and at least three things
   that did not work. The failures are what make it credible.

3. **The next six months.** Given what you now know, what is the next thing worth going deep
   on? Write it down while the context is fresh.

**Proof of understanding** — Re-read `my-bio.txt` from Day 0 and rewrite it. If nothing in it
changes, either you learned nothing or you are underselling six months of work — and the
second is more likely. The rewritten bio should make claims backed by numbers you can produce
on request.

**Reference** — Everything in `notes/`.

---

## Phase 8 exit checklist

- [ ] Maximum sustainable incident rate measured, defined by quality holding
- [ ] 100 randomized chaos scenarios run; every "wrong answer under stress" case fixed
- [ ] Full six-month cost history by version, with causes annotated
- [ ] On-prem breakeven recomputed with real utilisation data
- [ ] Ten ADRs written, at least three recording reversed decisions
- [ ] SENTINEL v1.0 tagged, documented, evaluation green, red-team passed
- [ ] All eight metrics compared against your Day 5 targets
- [ ] Retro written
- [ ] Phase deliverable #9 published
- [ ] Bio rewritten with claims you can back with numbers

---

## What you can do now that you could not on Day 1

Not a summary — a checklist you should be able to answer yes to. If any are no, you know
exactly which days to revisit.

- Write an agent loop from scratch, with no framework, from memory
- Compute cost and p95 latency for a proposed agent design in under two minutes
- Build a retrieval eval set and tell whether a retrieval change is real or noise
- Argue, with your own data, when multi-agent architecture is not worth it
- Make an agent survive process death and resume correctly, and prove it
- Validate an LLM judge against human labels and report kappa
- State the minimum detectable effect of your eval suite and refuse claims below it
- Derive KV cache size, concurrency ceiling and GPU count from first principles
- Compute an on-prem versus API breakeven from utilisation
- Decide whether to fine-tune, with a payback period
- Design an AI system end to end with capacity, failure modes, evals and a threat model
- Red-team an agent and state its residual risk honestly

That last one — stating residual risk honestly — is the whole discipline in one line.

---

**Back to:** [README](../README.md)
