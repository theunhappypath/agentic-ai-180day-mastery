# Phase 3 — Multi-Agent Orchestration & Durable Execution
**Days 67–96 · 5 weeks**

This is the phase closest to what you already do well, and therefore the one where it is
easiest to coast. Don't. You have built orchestration with approval gates; what this phase
adds is the discipline of *durability* — state that survives process death — and the
willingness to prove, with numbers, that the orchestration is earning its complexity.

The phase opens by arguing against itself. That is deliberate.

**Phase deliverable:** *When multi-agent is the wrong answer.*
**Capstone milestone:** SENTINEL v0.3 — supervisor, parallel hypothesis agents, verifier,
reporter, on a durable resumable workflow with enforced budgets.

---

## Week 12 — Topology and state

### Day 67 — When multi-agent is the wrong answer
**Concept (40 min)** — Multi-agent architectures are adopted far more often than they are
justified. Every agent boundary costs you: context that must be serialized and re-explained,
latency that compounds, failure modes that multiply, cost that scales with the number of
agents, and debuggability that collapses. A single agent with good tools beats a five-agent
system on most tasks. The legitimate reasons to split are genuine parallelism, genuinely
different context requirements, genuinely different privilege levels, and the need for an
independent verifier that has not seen the reasoning it is checking.

**Practical (80 min)** — Write `sentinel/orchestration/WHY-MULTI-AGENT.md` *before* you
build anything. For SENTINEL, argue explicitly which boundaries are justified and by which
of the four reasons. Then, for each proposed boundary, write down the measurement that would
prove you wrong.

**Proof of understanding** — Name at least one boundary you were tempted by and rejected.
If you justified all of them, you are rationalising — go again.

**Reference** — "Cognition: Don't Build Multi-Agents" and Anthropic's multi-agent research
system write-up. Read both; they disagree, and the disagreement is instructive.

---

### Day 68 — Topologies
**Concept (40 min)** — The vocabulary: **supervisor/worker** (a coordinator delegates and
aggregates — most common, clearest failure semantics); **pipeline** (fixed stages, each
transforming — simple, rigid); **blackboard** (agents read and write shared state
opportunistically — flexible, hard to reason about); **debate** (agents argue to surface
error — expensive, occasionally worth it for high-stakes judgments); **hierarchical**
(supervisors of supervisors — usually a smell at your scale).

**Practical (80 min)** — Implement supervisor/worker and pipeline for the same SENTINEL
sub-problem: gathering evidence across four sources. Measure latency, token cost, and
behaviour when one worker fails.

**Proof of understanding** — Report the failure-handling difference. In a pipeline, stage 3
failing means stages 1–2 are wasted work. In supervisor/worker, one worker failing may be
survivable. Quantify that with an actual injected failure.

**Reference** — "AutoGen"; "MetaGPT"; the Anthropic multi-agent write-up.

---

### Day 69 — Handoffs and what *not* to pass
**Concept (40 min)** — The hardest question in multi-agent design is what crosses the
boundary. Pass everything and you have paid the cost of splitting while keeping none of the
benefit — plus you have duplicated the context window. Pass too little and the sub-agent
lacks what it needs and hallucinates the gap. The right answer is usually a *structured
brief*: the objective, the specific constraints, the evidence already gathered in compressed
form, and explicitly what is out of scope.

**Practical (80 min)** — Design SENTINEL's handoff schema as a typed structure, not free
text. Implement three variants — full context, structured brief, and minimal objective-only
— and measure sub-agent output quality and token cost for each.

**Proof of understanding** — Report quality against handoff size. There is a point where
more context stops helping and starts hurting (Day 4 again). Find yours.

**Reference** — Your Day 33 compaction work — the same problem, at a different boundary.

---

### Day 70 — Orchestration state modelling
**Concept (40 min)** — Three ways to model agent control flow. **Finite state machine** —
explicit states and transitions, trivially serializable, rigid. **Graph** — nodes and
conditional edges, more expressive, what LangGraph provides. **Workflow engine** — durable
steps with an execution history, what Temporal-style systems provide, with the strongest
guarantees and the heaviest operational footprint. The choice determines what your failure
recovery can possibly look like.

**Practical (80 min)** — Model SENTINEL's investigation flow all three ways on paper. Then
implement the graph version, with state as an explicit typed object that every node reads
from and writes to. Every state mutation must be serializable to JSON.

**Proof of understanding** — Serialize your orchestration state mid-investigation and
inspect the JSON. Anything not in that file cannot survive a restart. Find at least one
thing you assumed was state and had actually left in a local variable.

**Reference** — LangGraph documentation; Temporal's durable execution documentation.

---

### Day 71 — **[BUILD]** SENTINEL orchestrator as an explicit graph
**Concept (40 min)** — Convert Day 16's single-agent state machine into a multi-node graph
with the boundaries you justified on Day 67 — and no others.

**Practical (80 min)** — Implement the graph: triage → supervisor → (evidence gathering) →
hypothesis formation → verification → report → human gate. State is one typed, serializable
object. Every node is a pure function of state to state. Run the corpus.

**Proof of understanding** — Draw the graph and confirm every edge condition is a function
of serialized state, not of anything held in memory. If any edge depends on a closure or a
local, it will break under resume — fix it now.

**Reference** — Your Day 67 justification document.

---

### Day 72 — **[CONSOLIDATE]** Did splitting help?
**Concept (40 min)** — The honest check. You added complexity; measure whether it bought
anything before building four more weeks on top of it.

**Practical (80 min)** — Run the corpus against the v0.2 single agent and the v0.3-in-
progress graph. Compare accuracy, cost, p95 latency and debuggability (how long does it take
you to diagnose a failure in each?). Write `notes/day-072.md`. Spaced review: Days 16 and 62.

**Proof of understanding** — State plainly whether the multi-agent version is better yet.
Early in a phase it frequently is not. Recording that honestly now is what makes the Day 95
comparison meaningful.

**Reference** — Your Day 65 v0.2 metrics.

---

## Week 13 — Durability

### Day 73 — Checkpointing and resumability
**Concept (40 min)** — A long investigation must survive process death, deployment,
and an approval pause that lasts overnight. Checkpointing means persisting state at
well-defined points such that resume produces the same outcome as an uninterrupted run. The
subtleties: what granularity (every node, or every tool call?), what about the tool call
that was in flight, and how do you avoid re-charging for work already done?

**Practical (80 min)** — Implement checkpointing after every node transition. Persist to
SQLite with a run ID and a monotonic step counter. Implement resume from any checkpoint.
Then test properly: kill the process at 10 different points across a run and verify each
resumes correctly.

**Proof of understanding** — Report how many of your 10 kill points resumed correctly on the
first attempt. It will not be 10. The failures are almost always in-flight side effects —
which is exactly Day 74.

**Reference** — Temporal's durable execution model; write-ahead logging fundamentals.

---

### Day 74 — Idempotency and event sourcing for agent steps
**Concept (40 min)** — Resume replays. If replaying a step re-executes a side effect, resume
is corrupting rather than recovering. Idempotency keys make repeated execution safe. Event
sourcing — storing the sequence of events rather than mutable state — makes the full history
auditable and lets you reconstruct any point in time, which turns out to be exactly what an
incident audit trail needs.

**Practical (80 min)** — Convert SENTINEL's state persistence to an append-only event log:
`ToolCalled`, `ToolReturned`, `HypothesisFormed`, `ApprovalRequested`, `ApprovalGranted`.
State becomes a fold over events. Add idempotency keys to every tool call so replay is safe.

**Proof of understanding** — Replay a full investigation from its event log and produce
byte-identical final state. Then kill mid-tool-call and show that resume does not double-
execute. That double-execution bug is the one that bites in production.

**Reference** — "Event Sourcing" (Fowler); your own distributed systems experience.

---

### Day 75 — LangGraph internals
**Concept (40 min)** — Read the source, not the tutorials. Understand how it represents
state, how checkpointers work, how interrupts suspend and resume execution, and how it
handles concurrent branches. The goal is to see which of your hand-built mechanisms it
already provides correctly and which it does differently for reasons worth understanding.

**Practical (80 min)** — Port one SENTINEL sub-flow to LangGraph using its checkpointer and
interrupt mechanism. Compare against your implementation on: lines of code, resume
correctness, observability, and how hard a custom termination condition is.

**Proof of understanding** — Name one thing LangGraph does better than your implementation
and one thing your implementation does better for SENTINEL's needs. Both must be specific.

**Reference** — LangGraph source and documentation.

---

### Day 76 — Durable workflow engines for agents
**Concept (40 min)** — Temporal-style engines give you durable execution as a platform
guarantee: deterministic replay, automatic retries with backoff, timers that survive
restarts, and long-running workflows measured in days. The cost is a real operational
dependency and a programming model that constrains what you can do inside a workflow. For
agent systems with human approval gates that may sit for hours, the fit is strong.

**Practical (80 min)** — Model SENTINEL's investigation as a durable workflow with the
approval gate as a durable timer/signal. Even a local prototype teaches the model. Compare
against your event-sourced implementation on: what you had to build versus what you got.

**Proof of understanding** — Answer specifically: what does a workflow engine give SENTINEL
that your event log does not? If the honest answer is "not much at this scale," that is a
legitimate and defensible finding — write it down.

**Reference** — Temporal documentation, particularly determinism constraints.

---

### Day 77 — **[BUILD]** Kill-and-resume, proven
**Concept (40 min)** — Durability is not a feature you claim, it is a property you test.
Build the test harness that proves it continuously.

**Practical (80 min)** — Build `sentinel/evals/chaos_resume.py`: runs an investigation,
kills the process at a random point, resumes, and asserts the final result matches an
uninterrupted run. Run it 50 times across the corpus. Fix every mismatch.

**Proof of understanding** — Report your resumption correctness rate across 50 randomized
kills. This is one of your eight success metrics. Target is 100%, and anything less has a
specific, findable cause.

**Reference** — Your Day 74 event log.

---

### Day 78 — **[CONSOLIDATE]** Durability review
**Concept (40 min)** — Consolidate the week: what state exists, where it lives, what
survives a crash, what is idempotent, and what the recovery semantics are for each failure
class.

**Practical (80 min)** — Write `sentinel/orchestration/DURABILITY.md` documenting all of it.
Include the list of things that are *not* durable and why that is acceptable. Spaced review:
Days 32 and 70.

**Proof of understanding** — The document lets someone else predict exactly what happens if
the process dies during any given node. That predictability is the deliverable.

**Reference** — Your chaos test results.

---

## Week 14 — Parallelism and failure

### Day 79 — Fan-out and fan-in over agents
**Concept (40 min)** — Parallelism is the strongest justification for multi-agent
architecture, and incident response is genuinely parallel: five candidate root causes can be
investigated simultaneously. The design questions are how you generate the branches, how you
bound them, how you merge results that may contradict each other, and what you do when one
branch fails or hangs.

**Practical (80 min)** — Implement fan-out over hypothesis agents in SENTINEL: the
supervisor generates N candidate hypotheses, spawns an investigator per hypothesis with a
per-branch budget, and merges. Implement the merge as an explicit ranking over evidence
strength, not as "ask a model to pick."

**Proof of understanding** — Report wall-clock latency for N=1, 3, 5 parallel branches
against total token cost. Parallelism buys latency with money. State the exchange rate you
measured and whether SENTINEL's budget can afford it.

**Reference** — Anthropic's multi-agent research system write-up on parallel subagents.

---

### Day 80 — Concurrency limits, rate limits and backpressure
**Concept (40 min)** — Fan-out meets reality: provider rate limits, your GPU's concurrency
ceiling, and the token-bucket behaviour of both. Without backpressure, fan-out produces a
burst of 429s, retries that amplify the burst, and a latency profile far worse than serial
execution. This is standard distributed systems work and it transfers directly.

**Practical (80 min)** — Implement a concurrency-limited executor with a semaphore, a token
bucket for rate limiting, and exponential backoff with jitter on 429. Then deliberately
exceed your rate limit and watch the difference between having and not having backpressure.

**Proof of understanding** — Plot p95 latency against fan-out width, with and without
backpressure. The un-backpressured curve gets *worse* past a point. Find that point — it is
your real maximum fan-out.

**Reference** — "Exponential Backoff And Jitter"; your provider's rate limit documentation.

---

### Day 81 — Failure recovery and compensation
**Concept (40 min)** — Distinguish failure classes: transient (retry), permanent (fail the
branch, keep the others), partial (three of five branches succeeded — is that a result?), and
poisonous (the input itself causes failure). For anything with side effects, you need
compensation — the saga pattern — because agents cannot roll back a transaction they made
through a tool.

**Practical (80 min)** — Build a failure taxonomy for SENTINEL and a policy for each class.
Implement partial-result handling: if three of five hypothesis branches complete, produce a
ranked report with an explicit confidence penalty rather than failing outright. Implement
compensation for the one mutating action you have.

**Proof of understanding** — Show SENTINEL producing a useful, honestly-caveated report from
a partial failure. A system that returns nothing when 60% succeeded is a system nobody trusts
during an outage.

**Reference** — "Sagas" (Garcia-Molina & Salem); your own distributed systems experience.

---

### Day 82 — Poison messages, dead-letter and the retry budget
**Concept (40 min)** — Some inputs fail every time. Without a retry budget and a dead-letter
path, they consume the entire system. Agents make this worse: a retry is not free like an
HTTP retry, it costs real money, and an agent may produce a *different* failure each attempt,
which defeats naive dedup. You need a retry budget denominated in dollars, not attempts.

**Practical (80 min)** — Implement a per-investigation retry budget in dollars. Implement
dead-lettering: an investigation that exhausts its budget is parked with full state for human
inspection, not discarded. Craft a deliberately poisonous corpus case — one with contradictory
telemetry — and confirm it dead-letters cleanly instead of burning the budget.

**Proof of understanding** — State your retry budget in dollars and how you derived it from
the value of a resolved incident. "Three retries" is a number someone made up; a budget tied
to value is an engineering decision.

**Reference** — Your `costs.jsonl`.

---

### Day 83 — **[BUILD]** Parallel hypothesis investigation
**Concept (40 min)** — Integration: fan-out with backpressure, per-branch budgets, partial
results, and the merge — all durable, so a crash mid-fan-out resumes correctly.

**Practical (80 min)** — Wire it together. Run the corpus. Run the chaos resume test against
the parallel version specifically — concurrent branches make resume substantially harder.

**Proof of understanding** — Report resumption correctness for the parallel version. If it
dropped from Day 77's number, the cause is in-flight branch state. Find it and fix it.

**Reference** — Your Day 77 chaos harness.

---

### Day 84 — **[CONSOLIDATE]** Latency budget review
**Concept (40 min)** — Time to hypothesis is one of your eight metrics and parallelism was
supposed to be how you protect it. Check whether it worked.

**Practical (80 min)** — Break down p50 and p95 time to hypothesis by phase: triage,
evidence gathering, hypothesis fan-out, verification, reporting. Find the dominant
contributor. Spaced review: Days 2 and 79.

**Proof of understanding** — Name the phase that dominates p95. It is frequently *not* the
one you expected, and it determines what Phase 5's optimisation work should target.

**Reference** — Your OTel traces.

---

## Week 15 — Planning and reflection

### Day 85 — Planning: decomposition and plan validation
**Concept (40 min)** — Explicit planning makes agent behaviour auditable and interruptible —
a human can approve or edit a plan before execution, which is the single strongest
human-in-the-loop control point. It also introduces a new failure mode: confidently wrong
plans executed faithfully. Plan *validation* — checking a plan against known constraints
before executing — catches much of that cheaply.

**Practical (80 min)** — Add explicit planning to SENTINEL: the supervisor produces a
structured investigation plan before acting. Implement validation — every referenced service
exists, every tool in the plan is available, the estimated cost is within budget, and the
plan's steps actually address the alert. Reject and replan on failure.

**Proof of understanding** — Report how often plan validation rejects a first plan. If it is
near zero, your validation is too weak to be doing anything. If it is above 40%, planning is
not working and you should say so.

**Reference** — "Plan-and-Solve Prompting"; "ReAct" (contrast the two, again, with a real
system this time).

---

### Day 86 — Replanning, and when planning hurts
**Concept (40 min)** — A plan made before any evidence exists is a guess. The value of
planning depends on how much reality diverges from expectation — high-divergence domains
punish rigid plans. Replanning triggers matter: after a step fails, after a step produces an
unexpected result, or at fixed checkpoints. Each replan costs a model call, so triggering on
everything is just expensive ReAct.

**Practical (80 min)** — Implement replanning with explicit triggers. Compare three
configurations on the corpus: plan-once, replan-on-failure, and replan-on-surprise (where
"surprise" is defined by evidence contradicting the plan's assumption). Measure accuracy,
cost and latency.

**Proof of understanding** — Report which configuration won. Then name the incident category
where plan-once was actually better — there will be one, usually the simple, well-covered
cases where replanning just burns money.

**Reference** — Your Day 15 ReAct versus plan-execute comparison, now with real data.

---

### Day 87 — Search over agent actions
**Concept (40 min)** — When the action space is large and steps are cheap to evaluate, tree
search beats greedy selection: generate multiple candidate next steps, evaluate them, expand
the promising ones. Tree-of-Thoughts and MCTS-style approaches formalise this. The catch is
cost — it multiplies model calls — so it is justified only when the evaluation signal is
strong and the stakes are high.

**Practical (80 min)** — Implement a shallow tree search over hypothesis refinement: at each
step generate 3 candidates, score them against retrieved evidence, expand the best 1. Depth
3. Compare against greedy on accuracy and cost.

**Proof of understanding** — Report accuracy gain per dollar for search versus greedy. Then
decide whether SENTINEL keeps it. For most production systems the honest answer is no — but
knowing why, in numbers, is worth the day.

**Reference** — "Tree of Thoughts: Deliberate Problem Solving with Large Language Models."

---

### Day 88 — Reflection, verifiers, and when self-critique degrades output
**Concept (40 min)** — Asking a model to critique its own output helps in some settings and
measurably hurts in others — models often "fix" correct answers into wrong ones and reflection
tends to reinforce rather than correct reasoning errors. A *separate* verifier that has not
seen the reasoning, and that checks claims against evidence rather than against plausibility,
is a stronger design than self-reflection.

**Practical (80 min)** — Implement both for SENTINEL: (1) self-reflection where the
investigator critiques its own hypothesis, and (2) an independent verifier agent that receives
only the hypothesis and the evidence — never the reasoning — and checks whether the evidence
actually supports the claim. Measure both on the corpus, tracking *flips*: correct→wrong and
wrong→correct.

**Proof of understanding** — Report the flip matrix for both approaches. If self-reflection
produces more correct→wrong flips than wrong→correct, it is actively harming you. This is
common and almost never measured.

**Reference** — "Large Language Models Cannot Self-Correct Reasoning Yet"; "Reflexion" — read
both and note where they conflict.

---

### Day 89 — **[BUILD]** Planner and verifier in SENTINEL
**Concept (40 min)** — Integrate the winners from Days 85–88 only. Anything that did not
earn its cost stays out — this discipline is the phase's real lesson.

**Practical (80 min)** — Wire in planning with validation, the chosen replan trigger, and the
independent verifier. The verifier's output feeds the confidence score on each hypothesis.
Run the corpus.

**Proof of understanding** — Report **false confidence rate** before and after adding the
verifier. This is the metric the verifier exists to move. If it did not move, the verifier is
theatre.

**Reference** — `sentinel/SPEC.md` success metrics.

---

### Day 90 — **[CONSOLIDATE]** Confidence and calibration
**Concept (40 min)** — A confidence score that does not correlate with correctness is worse
than no score, because people act on it. Calibration means that hypotheses you label 80%
confident are correct about 80% of the time.

**Practical (80 min)** — Plot a reliability diagram for SENTINEL: predicted confidence
against observed accuracy across the corpus. Compute expected calibration error. Spaced
review: Days 9 and 63.

**Proof of understanding** — Report your ECE. Models are typically overconfident — if your
80%-confidence hypotheses are right 55% of the time, say so, and note it as a Phase 4 target.

**Reference** — "On Calibration of Modern Neural Networks."

---

## Week 16 — Budgets, humans, and the honest comparison

### Day 91 — Human-in-the-loop at scale
**Concept (40 min)** — One approval gate is easy. A hundred concurrent investigations
generating approval requests is a queueing problem with a human as the bottleneck. You need:
prioritisation, timeout policies per action class, delegation rules (which actions can be
auto-approved under which conditions), batching of related approvals, and an audit trail that
records who approved what and on what evidence.

**Practical (80 min)** — Build the approval queue: priority ordering by incident severity,
per-action-class timeout policy, an auto-approve allowlist for read-only actions above a cost
threshold, and full audit logging. Simulate 20 concurrent investigations and measure human
decisions required per hour.

**Proof of understanding** — Report approvals-required-per-hour at 20 concurrent
investigations. If it exceeds what one on-call engineer can process, your system does not
scale, and the fix is delegation policy — not a faster model.

**Reference** — Your own SDLC platform's approval design, generalised.

---

### Day 92 — Budgets as first-class orchestration state
**Concept (40 min)** — Step budget, token budget, wall-clock budget and dollar budget should
be fields in your orchestration state, checked at every node transition, decremented by every
action, and inherited-and-split across fan-out branches. Not a wrapper. Not a `max_iterations`
constant. First-class state — because that is the only way a resumed run knows what it has
already spent.

**Practical (80 min)** — Implement a `Budget` type in orchestration state with all four
dimensions. Split it across parallel branches proportionally to hypothesis prior. Persist it
in the event log so resume does not reset spending. Enforce at every transition.

**Proof of understanding** — Kill an investigation at 60% budget consumption, resume it, and
show it correctly refuses to overspend. A resumed agent that resets its budget is how you get
a surprise bill.

**Reference** — Your Day 6 budget calculator, now runtime-enforced.

---

### Day 93 — Graceful degradation under budget pressure
**Concept (40 min)** — What should an agent do at 80% of budget? Not stop dead. It should
change strategy: stop exploring new hypotheses, consolidate what it has, skip verification on
weak branches, and produce a report that honestly states it was budget-limited. Designing the
degradation ladder is a real architectural exercise and it is what separates a demo from a
system.

**Practical (80 min)** — Implement the degradation ladder with explicit thresholds: at 60%
stop fan-out, at 80% skip low-priority verification, at 95% force report generation with
remaining evidence. Test by setting artificially low budgets across the corpus.

**Proof of understanding** — Report accuracy at 100%, 50% and 25% of normal budget. A good
system degrades gracefully — accuracy falls smoothly. A bad one falls off a cliff. Plot yours
and say which you built.

**Reference** — Your Day 81 partial-result handling.

---

### Day 94 — Multi-agent communication and shared memory
**Concept (40 min)** — When branches need to share findings — hypothesis B's investigator
discovers something that eliminates hypothesis D — you need a communication channel. Options:
a shared blackboard all branches read and write, supervisor-mediated messaging, or no sharing
at all (independent branches, merge at the end). Sharing improves efficiency and destroys
independence, which matters because independent branches are what make the merge meaningful.

**Practical (80 min)** — Implement a shared evidence blackboard that branches append to and
can read. Compare against fully independent branches on accuracy, cost and — critically —
whether branch conclusions became correlated.

**Proof of understanding** — Measure branch correlation with and without sharing. If shared
branches all converge on the same hypothesis, you have five agents doing one agent's work at
five times the cost. Quantify it.

**Reference** — Blackboard architecture literature; your Day 88 verifier independence
argument.

---

### Day 95 — **[BUILD]** SENTINEL v0.3 and the honest comparison
**Concept (40 min)** — The moment the phase has been building toward. You have a
sophisticated multi-agent orchestration. You also still have the v0.2 single agent. Run them
head to head and publish the result whatever it is.

**Practical (80 min)** — Full corpus run for both. Compare across all eight metrics plus
debuggability and lines of code. Tag `v0.3`. Update the changelog. Write
`notes/day-095-single-vs-multi.md` with the complete comparison.

**Proof of understanding** — State whether multi-agent won, on which metrics, and at what
cost multiple. A 4-point accuracy gain at 5× cost and 3× complexity is a *loss* for most
systems — and if that is your result, that is your Phase 3 write-up, and it is a far more
useful post than another architecture diagram.

**Reference** — Your Day 67 justification document. Check every prediction you made there.

---

### Day 96 — **[CONSOLIDATE]** Phase 3 review + publish
**Concept (40 min)** — The thesis: orchestration complexity must be justified by
measurement, durability is not optional for long-running agents, and most multi-agent systems
have never been compared against the single agent they replaced.

**Practical (80 min)** — Draft deliverable #4: **"When multi-agent is the wrong answer."**
Lead with the Day 95 head-to-head. Include the Day 88 flip matrix and the Day 94 branch
correlation number. Spaced review: Days 74 and 88.

**Proof of understanding** — Your write-up gives a reader a decision procedure for when to
split an agent, grounded in your measurements — not a survey of architectures.

**Reference** — Your `notes/` from Days 67–95.

---

## Phase 3 exit checklist

- [ ] A written justification for every agent boundary, with falsifying measurements
- [ ] Orchestration state fully serializable — proven by inspection, not assumption
- [ ] Event-sourced state with idempotent replay producing identical final state
- [ ] Chaos resume test: 50 randomized kills, correctness rate reported
- [ ] Fan-out with backpressure; maximum useful fan-out width measured
- [ ] Partial-result handling that produces useful, honestly-caveated output
- [ ] Independent verifier, with a measured effect on false confidence rate
- [ ] Calibration measured — you know your ECE
- [ ] Four-dimensional budgets as first-class state, surviving resume
- [ ] Graceful degradation ladder, with accuracy measured at 25/50/100% budget
- [ ] The honest single-agent versus multi-agent comparison, published
- [ ] SENTINEL v0.3 tagged
- [ ] Phase deliverable #4 drafted

**Next:** [Phase 4 — Evaluation, Observability & Reliability](phase-04-evaluation-reliability.md)
