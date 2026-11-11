# Phase 1 — Agent Primitives
**Days 13–36 · 4 weeks**

An agent is a loop: model produces a tool call, you execute it, you feed the result back,
repeat until a termination condition. Everything else — frameworks, graphs, swarms — is
scaffolding on top of that loop. You will build it by hand first, break it deliberately,
and only then look at what frameworks offer. You cannot evaluate abstractions over
machinery you have never had to maintain.

**Phase deliverable:** *Build the agent loop before you pick a framework.*
**Capstone milestone:** SENTINEL v0.1 — single agent, six diagnostic tools, MCP server,
approval gate, 20-case incident corpus.

---

## Week 3 — The loop, from first principles

### Day 13 — Tool calling from scratch, no framework
**Concept (40 min)** — The raw mechanics: you send the model a list of tool definitions
(name, description, JSON Schema for inputs); it may respond with a `tool_use` block instead
of text; you execute it yourself and append a `tool_result` block to the conversation; you
call again. That is the entire protocol. Frameworks hide this, and when something goes
wrong at step 14 of an investigation, the hiding is what costs you the afternoon.

**Practical (80 min)** — In `drills/day-013-rawloop/`, write ~150 lines of Python against
the Messages API directly: no agent SDK, no LangChain, no helpers. Two tools —
`get_current_time` and `read_file`. Print every request and response in full. Run a task
requiring two sequential tool calls.

**Proof of understanding** — Draw the exact message array after a 2-tool-call
conversation, block by block, from memory. If you can't, read your own logs until you can.

**Reference** — Anthropic Messages API tool use documentation.

---

### Day 14 — Tool schema design
**Concept (40 min)** — The tool description and schema *are* prompt engineering, and they
are the highest-leverage prompt surface you have. Parameter names, descriptions, enums
versus free strings, required versus optional, and what you say about *when* to use the
tool determine call accuracy far more than the system prompt does. An enum of 12 valid
service names eliminates an entire class of hallucination that no amount of instruction
will.

**Practical (80 min)** — Take one tool — `search_logs` — and write five schema variants:
minimal, verbose description, enum-constrained parameters, with usage examples embedded in
the description, and one deliberately ambiguous. Build a 25-case test set of user requests
with known-correct tool arguments. Measure argument accuracy per variant.

**Proof of understanding** — Report the accuracy spread across variants. It is typically
much larger than people expect. Name the single schema change that bought the most
accuracy, and why.

**Reference** — Anthropic tool use best practices documentation; JSON Schema specification.

---

### Day 15 — ReAct versus plan-and-execute
**Concept (40 min)** — Two foundational control flows. **ReAct** interleaves reasoning and
acting — decide the next step given everything so far. Adaptive, but it drifts on long
horizons and can loop. **Plan-and-execute** produces a full plan up front, then executes
steps. Cheaper and auditable, but brittle when reality diverges from the plan. Real systems
are usually a hybrid, and knowing *why* you chose the hybrid is the skill.

**Practical (80 min)** — Implement both against the same tools and the same 15 tasks.
Instrument: steps taken, tokens consumed, wall time, success rate, and how each behaves
when a tool returns an unexpected error mid-run.

**Proof of understanding** — Report the success/cost tradeoff as a table. Then identify
the specific task category where plan-and-execute fails and explain the mechanism — it
will be a task where step 2's result should have changed the plan.

**Reference** — "ReAct: Synergizing Reasoning and Acting in Language Models";
"Plan-and-Solve Prompting."

---

### Day 16 — The agent loop as an explicit state machine
**Concept (40 min)** — A `while True` with a max-iterations guard is not an architecture.
Model the loop as a state machine with named states (PLANNING, CALLING_TOOL,
AWAITING_APPROVAL, SUMMARIZING, DONE, FAILED), explicit transitions, and termination
conditions that are separate concerns: goal achieved, step budget exhausted, token budget
exhausted, wall-clock exceeded, loop detected, unrecoverable error. Phase 3's durability
work is only possible if this state is explicit and serializable.

**Practical (80 min)** — Refactor Day 13's loop into a state machine with serializable
state. Add loop detection: hash (tool name + normalized args) and halt on the third
identical call. Add all five termination conditions. Force each one to fire and confirm
the agent exits cleanly with a useful partial result rather than a stack trace.

**Proof of understanding** — Trigger loop detection deliberately and show the agent
degrading gracefully — reporting what it learned before halting, not just dying.

**Reference** — Your Phase 0 budget calculator, now enforced as runtime state.

---

### Day 17 — **[BUILD]** SENTINEL skeleton and the incident corpus
**Concept (40 min)** — Re-read the corpus section of
[capstone-sentinel.md](capstone-sentinel.md). The corpus is the most valuable thing you
build in this phase — every evaluation for the next five months runs against it. Build it
before the agent gets good, so the agent is never tuned on data you invented to flatter it.

**Practical (80 min)** — Build 20 incident cases. Write a fault injector against a toy
3-service app that produces known failures — slow dependency, bad config push, memory
leak, cache stampede, retry storm — and capture real telemetry. Supplement by
reconstructing 5 cases from public postmortems. Every case gets a `ground-truth.json` with
root cause, fix, **and the minimal evidence set**. Port your Day 16 state machine into
`sentinel/agent/loop.py`.

**Proof of understanding** — Class balance. Report the distribution of root-cause
categories across your 20 cases. If any single category exceeds 35%, your agent will learn
that prior instead of learning to investigate.

**Reference** — Published cloud provider and infrastructure postmortems.

---

### Day 18 — **[CONSOLIDATE]** Reading traces like a debugger
**Concept (40 min)** — Debugging agents is a distinct skill: you read a conversation
transcript the way you read a stack trace. Learn the tells — a tool result that was too
long and pushed the goal out of attention range; a schema mismatch the model papered over;
the moment the agent stopped reasoning about the task and started reasoning about its own
previous output.

**Practical (80 min)** — Build `sentinel/agent/trace_viewer.py`: renders a run as a
readable timeline with per-step token counts, cumulative cost, latency, and state
transitions. Run all 20 corpus incidents through your v0 agent and read every transcript.

**Proof of understanding** — Write `notes/day-018.md` classifying the failures you saw
into the Day 12 taxonomy. Which taxonomy entry dominates? That is your Phase 2 priority.

**Reference** — Your `notes/failure-taxonomy.md`.

---

## Week 4 — Tools that survive contact with a model

### Day 19 — Tool design principles
**Concept (40 min)** — Tools are an API whose consumer is a stochastic, forgetful,
occasionally over-confident client. That client changes the design rules: prefer
idempotent operations; choose granularity carefully (too fine and the agent burns steps
composing them, too coarse and it cannot express what it needs); return shapes should be
small, structured and self-describing; and never make a destructive operation easy to call
by accident.

**Practical (80 min)** — Design SENTINEL's six diagnostic tools on paper first:
`search_logs`, `query_metrics`, `fetch_trace`, `get_deploy_history`, `search_code`,
`read_runbook`. For each: exact schema, return shape, error taxonomy, idempotency, and cost
in tokens of a typical result. Then implement two of them against your corpus.

**Proof of understanding** — For each tool, state its typical result size in tokens. Any
tool that routinely returns more than ~2000 tokens needs pagination or summarization —
find yours and say what you will do about it.

**Reference** — "Toolformer"; your own API design experience, which mostly transfers.

---

### Day 20 — Error messages as prompts
**Concept (40 min)** — When a tool fails, the error message goes straight into the model's
context and becomes an instruction. `KeyError: 'svc'` teaches the model nothing.
`Unknown service 'svc'. Valid services: api-gateway, auth, billing, ... Did you mean
'svc-auth'?` teaches it to recover on the next turn. This is the single cheapest
reliability improvement available to you, and it is almost universally neglected.

**Practical (80 min)** — Build an error taxonomy for your tools: invalid argument,
not found, empty result, timeout, permission denied, upstream failure. Write a recovery-
oriented message for each — what went wrong, what valid input looks like, and the suggested
next action. Then A/B raw exceptions versus designed errors across 30 runs where you inject
failures deliberately.

**Proof of understanding** — Report recovery rate for raw versus designed errors. Expect a
large gap. Note especially the empty-result case: an agent that cannot distinguish "no
matching logs" from "the search failed" will confidently conclude the wrong thing.

**Reference** — Your Day 14 tool schema work — same principle, applied to the return path.

---

### Day 21 — Validation and repair loops
**Concept (40 min)** — Layer the defenses: constrained decoding where available, schema
validation on receipt, semantic validation (is this service name real? is this timestamp
inside the incident window?), and a bounded repair loop that hands the validation error
back to the model. Bounded matters — an unbounded repair loop is a cost incident.

**Practical (80 min)** — Wrap every SENTINEL tool call in a validator. Add semantic checks
beyond the schema: service names must exist in the service registry, time ranges must
intersect the incident window, trace IDs must be well-formed. Implement repair with a hard
cap of 2 attempts, and log every repair to `costs.jsonl` with a `repair=true` tag.

**Proof of understanding** — Report your repair rate and the fraction of repairs that
succeed on attempt 1 versus 2. If attempt-2 repairs almost never succeed, cap it at 1 and
save the money — decide this from your data, not from a blog post.

**Reference** — Pydantic validation documentation; "Instructor" library patterns.

---

### Day 22 — Sandboxed code execution as a tool
**Concept (40 min)** — A code-execution tool is a step-change in capability — the agent can
compute, transform and analyse instead of reasoning about data in tokens. It is also the
single most dangerous tool you will ever expose, and the security model is not "the prompt
says be careful." It is process isolation, no network egress, a read-only filesystem
except one scratch directory, CPU and memory limits, and a hard timeout.

**Practical (80 min)** — Build a sandboxed Python execution tool: containerised, network
disabled, memory- and CPU-capped, 10-second timeout, results returned as structured output
with stdout/stderr separated. Give SENTINEL a real reason to use it — computing error-rate
deltas and percentile shifts across the metrics in an incident window. Then try to escape
your own sandbox for 20 minutes.

**Proof of understanding** — Document one thing you tried that the sandbox blocked, and
one thing you are not sure it would block. The second item goes into your Phase 7 threat
model.

**Reference** — gVisor and Firecracker documentation; OWASP guidance on sandboxing.

---

### Day 23 — **[BUILD]** SENTINEL's six diagnostic tools
**Concept (40 min)** — Review Days 19–22 as a checklist and apply it uniformly. Consistency
across a tool suite matters more than brilliance in any one tool — the model learns the
conventions of your toolset and generalises them.

**Practical (80 min)** — Implement all six tools completely against the corpus, each with:
designed schema, semantic validation, recovery-oriented errors, pagination for large
results, and a token-cost estimate returned in metadata. Run all 20 incidents end to end.

**Proof of understanding** — Record baseline metrics: root-cause accuracy@1 and @3, mean
tool calls per incident, mean cost per incident, p50 and p95 time to hypothesis. These are
your Day 23 baseline. Everything for the next 157 days is measured against them.

**Reference** — `sentinel/SPEC.md` — compare against the targets you set on Day 5.

---

### Day 24 — **[CONSOLIDATE]** Where the agent is actually failing
**Concept (40 min)** — Baselines are only useful if you interrogate them. Separate failures
into: the agent never retrieved the necessary evidence (a retrieval problem — Phase 2), it
retrieved it and reasoned wrongly (a reasoning/orchestration problem — Phase 3), or it was
right but not confident, or wrong but confident (a calibration problem — Phase 4).

**Practical (80 min)** — Manually review all 20 transcripts and label each with the
failure class above. Tally the distribution. Write `notes/day-024.md` with your honest
diagnosis. Spaced review: re-read Days 4 and 9.

**Proof of understanding** — State what fraction of failures were retrieval failures. In
almost every incident-response system this is the largest bucket — which is why Phase 2 is
30 days long. Confirm or refute that with your own data.

**Reference** — Your own transcripts. Nothing else.

---

## Week 5 — MCP: tools as infrastructure

### Day 25 — MCP protocol fundamentals
**Concept (40 min)** — The Model Context Protocol standardises how applications supply
context and capabilities to models — an open protocol between agent hosts and capability
servers. The strategic value is decoupling: your tools stop being functions inside one
Python process and become services that any compliant client can use. For someone who has
already integrated Claude, Cursor and OpenCode, this is the layer that makes that
integration stop being three bespoke adapters.

**Practical (80 min)** — Read the MCP specification properly — architecture, message flow,
lifecycle. Then run an existing reference server (filesystem or git) against a client and
watch the wire traffic: initialization, capability negotiation, tool listing, tool
invocation.

**Proof of understanding** — Diagram the full initialize → list → call → result sequence
with actual JSON-RPC messages from your capture, not from the docs.

**Reference** — Model Context Protocol specification; MCP reference server repositories.

---

### Day 26 — Tools versus resources versus prompts; transports
**Concept (40 min)** — MCP exposes three distinct primitives and conflating them is the
most common design error. **Tools** are model-invoked actions with side effects.
**Resources** are application-controlled context the client decides to include — data, not
actions. **Prompts** are user-invoked templates. Transports (stdio for local subprocess,
HTTP-based for remote) determine your trust boundary and your deployment story.

**Practical (80 min)** — Classify all six SENTINEL capabilities across the three
primitives. The runbook is genuinely ambiguous — is it a tool the agent calls or a resource
the client attaches? Argue both sides in writing, then decide. Prototype each transport and
note the operational differences.

**Proof of understanding** — Defend your runbook classification in writing. The right
answer depends on who should control inclusion — the model or the application — and that
is a real architectural decision, not a formality.

**Reference** — MCP specification sections on tools, resources, prompts and transports.

---

### Day 27 — Build your own MCP server
**Concept (40 min)** — Server implementation mechanics: declaring capabilities, handling
list and call requests, structuring errors, streaming progress on long operations, and
lifecycle management. Building one is how the protocol stops being abstract.

**Practical (80 min)** — Implement `sentinel-mcp`, exposing all six diagnostic tools over
stdio. Connect it to a real MCP client and drive an investigation through it. Handle the
awkward cases: a tool that takes 8 seconds, a tool returning 50KB, a tool that fails.

**Proof of understanding** — Your server works from a client you did not write. That
independence is the whole point — you have built infrastructure, not a function.

**Reference** — MCP Python SDK documentation.

---

### Day 28 — MCP clients, sampling, and the trust boundary
**Concept (40 min)** — The client side matters too: server discovery, connection
management, aggregating tools from multiple servers into one namespace, and handling
collisions. MCP also allows a server to request model completions from the client
(sampling) — powerful and a genuine trust question. Every third-party MCP server you
connect is code you did not write, receiving your context.

**Practical (80 min)** — Write a minimal MCP client that connects to two servers at once
and merges their toolsets, with collision handling. Then write `notes/mcp-trust.md`: what a
malicious MCP server could do to an agent that trusts it — exfiltrate context, return
poisoned tool results designed to redirect the agent, impersonate another server's tool.

**Proof of understanding** — Name the specific mechanism by which a poisoned tool *result*
— not a prompt — could redirect your agent. This is indirect prompt injection and it is
Phase 7's central threat. You should be uneasy.

**Reference** — MCP specification security considerations; "Prompt Injection" (Willison).

---

### Day 29 — **[BUILD]** SENTINEL over MCP
**Concept (40 min)** — Migrating from in-process tools to MCP is a real architectural
change: process boundaries, serialization cost, failure modes when a server dies, and
latency added per call. Measure it rather than assuming it's free.

**Practical (80 min)** — Cut SENTINEL over to consume its tools through `sentinel-mcp`.
Re-run all 20 incidents. Compare against the Day 23 baseline on accuracy, cost and latency.
Handle server crash and restart mid-investigation.

**Proof of understanding** — Report the per-call latency overhead MCP added. Decide, with
that number in hand, whether the decoupling is worth it for SENTINEL — and write down the
reasoning either way.

**Reference** — Your Day 23 baseline.

---

### Day 30 — **[CONSOLIDATE]** Tool suite review
**Concept (40 min)** — A toolset is a language you are designing for the model. Review it
for coherence: consistent naming, consistent error shapes, consistent pagination,
consistent time handling. Inconsistency forces the model to memorise exceptions instead of
generalising.

**Practical (80 min)** — Audit all six tools against the Days 19–21 principles and fix
every inconsistency. Re-run the corpus. Spaced review: re-read Days 14 and 20.

**Proof of understanding** — Report accuracy before and after the consistency pass. Pure
consistency work, no new capability — if it moved the number, that tells you something
worth publishing.

**Reference** — Your own tool implementations.

---

## Week 6 — Streaming, humans, and context economics

### Day 31 — Streaming: tokens, tool calls, and perceived latency
**Concept (40 min)** — Streaming changes user experience more than it changes actual
latency — TTFT becomes the number that matters, not total time. Streaming tool calls is
harder: arguments arrive as partial JSON, so you need incremental parsing to show "calling
search_logs on api-gateway…" before the call is complete. For a 90-second investigation,
this is the difference between a usable tool and one people abandon.

**Practical (80 min)** — Implement full streaming in SENTINEL: token streaming for
reasoning text, incremental tool-call argument parsing, and a step-level progress feed.
Build the Next.js console in `sentinel/ui/` that renders the investigation live.

**Proof of understanding** — Report TTFT versus total investigation time. Then articulate
what the user can meaningfully *do* with the stream — if the answer is "watch," you have
built a progress bar; if it's "notice it's on the wrong track and stop it," you have built
a control surface.

**Reference** — Anthropic streaming documentation; Vercel AI SDK streaming patterns.

---

### Day 32 — Human-in-the-loop primitives
**Concept (40 min)** — The primitives are: **approval** (pause before a gated action, wait
for a decision), **interrupt** (a human stops or redirects a running agent), and **resume**
(continue from a serialized state, possibly in a different process, possibly hours later).
Your existing SDLC platform has approval gates — this is where you generalise them into
primitives with clean semantics. The hard part is not the UI; it is that resume requires
your entire state to be serializable, which is why Day 16 mattered.

**Practical (80 min)** — Implement all three in SENTINEL. Gate every mutating action and
every action above a cost threshold. Serialize state to disk on pause. Prove resume works
by killing the process entirely, restarting, and continuing. Add a timeout policy — what
happens when nobody approves for 30 minutes?

**Proof of understanding** — Kill the process during an approval pause, restart it, and
resume to a correct result. Then state your timeout policy and defend it: auto-deny is safe
but useless at 3am; auto-approve is convenient and how outages get worse.

**Reference** — Your own SDLC platform's approval gate design.

---

### Day 33 — Context engineering: compaction, summarization, truncation
**Concept (40 min)** — Long investigations exhaust context. The available moves:
truncate old tool results (cheap, lossy), summarize completed sub-investigations (costs a
model call, preserves conclusions), externalize to a scratchpad file the agent can re-read
(cheap, requires the agent to remember to look), and structured state that carries forward
explicitly. Days 4 and 9 apply directly — what you keep, and *where* you put it, both
matter.

**Practical (80 min)** — Implement three strategies in SENTINEL and measure each against
the corpus: (1) naive truncation of oldest tool results, (2) summarize-on-threshold at 60%
context, (3) an externalized evidence scratchpad. Measure tokens saved **and** accuracy for
each.

**Proof of understanding** — Plot tokens saved against accuracy. There will be a strategy
that saves the most tokens and is not the best choice. Naming it, and saying why you
rejected it, is the deliverable.

**Reference** — "Lost in the Middle" (again — the position effects govern what compaction
should preserve).

---

### Day 34 — Agent framework survey, done adversarially
**Concept (40 min)** — Now — and only now — evaluate frameworks. You have hand-built the
loop, tool layer, state machine, HITL primitives and compaction. Look at Claude Agent SDK,
LangGraph, Pydantic AI and OpenAI Agents SDK and ask three questions of each: what does it
do that I built, what does it do that I did *not* build, and what does it prevent me from
doing?

**Practical (80 min)** — Reimplement one narrow slice of SENTINEL — a 3-tool investigation
loop — in two frameworks. Compare lines of code, what you lose visibility into, how hard
custom termination conditions are, and whether resume-from-serialized-state is supported or
fought.

**Proof of understanding** — Write `notes/framework-decision.md` with a decision and its
reasoning. "Keep the hand-rolled loop, adopt one library for a specific concern" is a
legitimate and common outcome. What is not legitimate is choosing by popularity.

**Reference** — Claude Agent SDK, LangGraph, Pydantic AI, OpenAI Agents SDK documentation.

---

### Day 35 — **[BUILD]** SENTINEL v0.1 complete
**Concept (40 min)** — Integration day. v0.1 = state-machine loop + six MCP tools +
validation and repair + designed errors + streaming + approval/interrupt/resume + a
compaction strategy + the trace viewer + a working console.

**Practical (80 min)** — Wire it all together and run the full corpus. Tag `v0.1`. Write
`sentinel/CHANGELOG.md` recording the metrics at this version.

**Proof of understanding** — v0.1 metrics versus the Day 23 baseline versus your Day 5
targets. Three columns. Some will have moved backwards — say so and explain why.

**Reference** — `sentinel/SPEC.md`.

---

### Day 36 — **[CONSOLIDATE]** Phase 1 review + publish
**Concept (40 min)** — What you now know that you did not on Day 13: the loop is simple and
everything hard lives in the tool layer, the error paths and the state model. That is the
thesis of your write-up.

**Practical (80 min)** — Draft deliverable #2: **"Build the agent loop before you pick a
framework."** Use your own numbers — the schema variant spread from Day 14, the error-
message recovery gap from Day 20, the MCP overhead from Day 29. Spaced review: Days 16 and 22.

**Proof of understanding** — The write-up contains at least four measurements someone else
could reproduce. Opinion pieces about agent architecture are abundant; measured ones are not.

**Reference** — Your `notes/` from Days 13–35.

---

## Phase 1 exit checklist

- [ ] You can write a working agent loop from scratch with no framework, from memory
- [ ] 20-case incident corpus exists with ground truth *and* minimal evidence sets
- [ ] Six diagnostic tools, all with semantic validation and recovery-oriented errors
- [ ] `sentinel-mcp` runs and works from a client you did not write
- [ ] Approval, interrupt and resume all work — proven by killing the process
- [ ] You have a written, reasoned framework decision
- [ ] SENTINEL v0.1 tagged, with metrics in the changelog
- [ ] Phase deliverable #2 drafted

**Next:** [Phase 2 — Context, Memory & Retrieval](phase-02-context-memory-retrieval.md)
