# Phase 7 — AI System Design & Security
**Days 157–174 · 3 weeks**

Two threads that belong together. **System design** is the ability to take an ambiguous
requirement and produce an architecture with capacity numbers, cost models, failure modes
and an evaluation strategy attached — the skill your bio calls "architecture-first
development," applied to AI systems. **Security** is the thread most agent projects
discover late and expensively, and it is inseparable from design: an agent's permission
model is an architectural decision, not a hardening step.

Six of these eighteen days are spent writing system designs for systems you will not build.
That is the point. Design fluency comes from repetition across varied problems, and the
constraint that you cannot implement your way out of a bad design is what forces the
thinking.

**Phase deliverable:** *Threat modelling an agent with production access.*
**Capstone milestone:** SENTINEL v0.7 — threat model, least-privilege tool scoping, egress
control, tamper-evident audit trail, multi-tenancy.

---

## Week 27 — The design method

### Day 157 — A repeatable AI system design framework
**Concept (40 min)** — A framework you can run under time pressure, in order:
**(1) Requirements** — who uses it, what does success mean, what volume.
**(2) Constraints** — latency budget, cost ceiling, data residency, privacy, accuracy floor.
**(3) Quality bar** — what accuracy is required, and what happens when it is not met.
**(4) Capacity** — requests, tokens, GPUs, storage.
**(5) Topology** — models, retrieval, orchestration, humans.
**(6) Failure modes** — what breaks, what degradation is acceptable.
**(7) Evaluation** — how you know it works, before and after launch.
**(8) Security** — trust boundaries, permissions, injection surface.
Most AI design discussions start at (5) and never reach (7) or (8). Starting at (1) and
insisting on (3) is what makes the difference.

**Practical (80 min)** — Write the framework as a template in `designs/TEMPLATE.md` with
prompting questions under each heading. Then apply it retroactively to SENTINEL and see what
you never answered properly — there will be several, and one of them will be the quality bar.

**Proof of understanding** — Name the framework step SENTINEL is weakest on. For most
self-directed projects it is (3), because nobody made you commit to an accuracy floor.

**Reference** — Your own architecture practice; `sentinel/SPEC.md`.

---

### Day 158 — Capacity and cost estimation under time pressure
**Concept (40 min)** — The estimation chain, done in your head or on a whiteboard:
users → requests/day → requests/second peak (apply a 3–10× peak factor) → model calls per
request → tokens per call → tokens/second → GPUs required (from Phase 5's capacity model) or
API spend. Then storage: documents → chunks → vectors → bytes. Being able to run this in two
minutes is what separates a credible AI architect from someone describing boxes.

**Practical (80 min)** — Do five estimation drills, timed at 10 minutes each: a customer
support agent for 10k daily users; code review on 5k PRs a day; a document Q&A over 50M
documents; a voice agent handling 500 concurrent calls; SENTINEL at 200 incidents a day.
Produce GPU count, monthly cost, and storage for each.

**Proof of understanding** — For each drill, state which single assumption most changes the
answer. It is usually tokens per call or the peak factor — and knowing which lever dominates
is what lets you sanity-check someone else's estimate in real time.

**Reference** — Your Phase 5 capacity model and `costs.jsonl` rates.

---

### Day 159 — Design #1: real-time voice agent
**Concept (40 min)** — The design that latency dominates completely. Sub-800ms
response is table stakes for natural conversation, and the pipeline is
speech-to-text → LLM → text-to-speech, each adding latency. This forces architectural
choices you would never make otherwise: streaming everything, speculative response
generation, small models with aggressive prompt caching, interruption handling, and turn
detection as a first-class component. Nothing in the Phase 5 toolkit is optional here.

**Practical (80 min)** — Write `designs/01-voice-agent.md` in full using the template. Budget
every millisecond across the pipeline. Address barge-in, ASR errors propagating into the LLM,
and what the system does when the LLM exceeds its budget mid-turn.

**Proof of understanding** — Your latency budget sums to under 800ms with each component
justified. Then state which component you would cut first under pressure and what it costs
you in quality.

**Reference** — Your Day 139 latency budgeting method.

---

### Day 160 — Design #2: multi-tenant RAG SaaS
**Concept (40 min)** — The design that isolation dominates. Every tenant's data must be
invisible to every other tenant — through the index, through the cache, through the model,
and through error messages. The hard parts: index-per-tenant versus shared-index-with-filter
(a correctness and cost tradeoff with real security consequences), noisy neighbours, per-tenant
quota and cost attribution, and prompt caching that must not leak a shared prefix containing
tenant data.

**Practical (80 min)** — Write `designs/02-multitenant-rag.md`. Decide the isolation model
explicitly and state the failure mode of the alternative. Design quota enforcement, per-tenant
cost attribution, and the cache key scheme that makes cross-tenant leakage structurally
impossible rather than merely unlikely.

**Proof of understanding** — Describe the specific bug in a shared-index-with-metadata-filter
design that leaks tenant A's data to tenant B. It is a one-line mistake and it is the reason
serious deployments choose physical isolation for sensitive tenants.

**Reference** — Your Day 47 index architecture.

---

### Day 161 — **[BUILD]** Multi-tenancy in SENTINEL
**Concept (40 min)** — Apply Day 160 to your own system. SENTINEL serving multiple teams
means per-team indexes, per-team service graphs, per-team budgets and strict isolation.

**Practical (80 min)** — Implement a tenant model: tenant-scoped retrieval, tenant-scoped
memory, per-tenant budget from Day 92's budget type, and tenant-scoped cache keys. Then write
a test that *attempts* cross-tenant access through every path — retrieval, memory, cache,
error messages — and asserts failure.

**Proof of understanding** — Your cross-tenant test suite covers every data path, not just
the obvious one. List the paths. Cache and error messages are the ones people miss.

**Reference** — Your Day 64 caching implementation — check its keys carefully.

---

### Day 162 — **[CONSOLIDATE]** Design review of your own designs
**Concept (40 min)** — Review Designs #1 and #2 as an adversarial reviewer would. The
questions that expose weak designs: what happens at 10× volume, what happens when the model
provider has an outage, what does this cost at peak, how do you know it works, and what does a
malicious user get.

**Practical (80 min)** — Write a critique of both designs and revise them. Spaced review:
Days 118 and 133.

**Proof of understanding** — Each design has at least one substantive flaw you found and
fixed. A design you cannot criticise is a design you have not examined.

**Reference** — `designs/TEMPLATE.md`.

---

## Week 28 — Design repetition and data architecture

### Day 163 — Design #3: coding agent for a 1000-engineer org
**Concept (40 min)** — The design closest to your own experience, and therefore the one to be
most rigorous about. The hard parts are not the agent: repository-scale context (millions of
files, no context window is enough), incremental indexing as code changes continuously,
permissions inherited from source control, running untrusted generated code safely, review and
merge workflow integration, and cost control across a thousand engineers who will use it far
more than you projected.

**Practical (80 min)** — Write `designs/03-coding-agent.md`. Address indexing freshness for a
monorepo with 500 commits a day, per-engineer cost attribution and quota, and the security
model for an agent that can read every repository. Compare against what you actually built —
and be specific about what you would do differently.

**Proof of understanding** — State the indexing strategy for a repository that changes faster
than you can fully re-index. The answer involves incremental updates and staleness tolerance
per content type, and it is a genuinely hard design problem.

**Reference** — Your own AI SDLC platform experience; Day 40's AST chunking.

---

### Day 164 — Design #4: agentic search
**Concept (40 min)** — A search system where an agent plans queries, reads results, and
iterates — with the whole open web as an untrusted input. Design pressures: latency (users
expect search to be fast, agents are slow), cost per query at consumer scale, freshness,
source quality assessment, citation and attribution, and the fact that **every retrieved page
is attacker-controlled input** — which makes this the cleanest illustration of indirect
prompt injection you will design.

**Practical (80 min)** — Write `designs/04-agentic-search.md`. Address the cost problem at
consumer scale (this is where cascades and caching stop being optimisations and become
existential), source trust scoring, and the injection surface of reading arbitrary web pages.

**Proof of understanding** — Describe the mechanism by which a web page could redirect an
agentic search system's behaviour, and the specific mitigation you designed. This is the
central problem of Day 169 and you should arrive there having already thought about it.

**Reference** — Your Day 28 MCP trust notes.

---

### Day 165 — Design #5: document processing at scale
**Concept (40 min)** — A batch-oriented design, which changes everything: latency barely
matters, throughput and cost dominate, and batch APIs or dedicated serving become the obvious
choice. The hard parts are heterogeneous document formats, OCR quality propagating downstream,
extraction schema evolution, quality assurance at a volume no human can review, and the
reprocessing problem — when you improve the pipeline, do you reprocess 50 million documents?

**Practical (80 min)** — Write `designs/05-document-pipeline.md` for 10M documents a month.
Address sampling-based QA (how many documents must you review to bound the error rate — use
Day 109's methodology), schema evolution, and the reprocessing cost model.

**Proof of understanding** — State the sample size needed to bound extraction error within
1% at 95% confidence, and the resulting human review cost per month. Quality assurance at
scale is a sampling problem, and treating it as one is the insight.

**Reference** — Your Day 109 statistical work.

---

### Day 166 — Design #6: on-prem enterprise copilot
**Concept (40 min)** — The design where constraints dominate capability: no data leaves the
network, so no frontier API; hardware is fixed and procured slowly; the model is whatever you
can serve; compliance and audit requirements are contractual; and users compare it to
consumer products they use at home. Everything from Phase 5 applies directly, and the design
question becomes how to deliver acceptable quality within a hard capability ceiling.

**Practical (80 min)** — Write `designs/06-onprem-copilot.md` for a 5000-employee company on
fixed hardware. Address capability gap mitigation (better retrieval and better tools
compensating for a weaker model), capacity planning against a fixed GPU count, and the audit
requirements. This is your bio's territory — make it your strongest design.

**Proof of understanding** — State the concrete techniques by which a weaker on-prem model
plus excellent retrieval and tooling reaches acceptable quality, with reference to your own
measured results from Phases 2 and 5. You have the numbers to make this argument
quantitatively — very few people do.

**Reference** — Your Phase 5 measurements; your own migration experience.

---

### Day 167 — **[BUILD]** Data architecture: freshness, refresh and deletion
**Concept (40 min)** — The unglamorous layer that determines whether a system stays correct.
Ingestion pipelines, index refresh strategy (full rebuild versus incremental, and the
consistency window between them), staleness tolerance per content type, and deletion — which
is a genuine architectural problem, because a deleted document must vanish from the vector
index, the lexical index, the cache, the memory store, and any summary derived from it.

**Practical (80 min)** — Implement SENTINEL's data lifecycle: incremental index updates,
per-source staleness budgets, and a deletion path that provably removes a document from every
store including derived summaries and caches. Write a test that deletes a document and asserts
it is unreachable through every retrieval path.

**Proof of understanding** — Your deletion test covers derived data — summaries and semantic
memories that *contain* information from the deleted document. That is the hard case and the
one that turns a deletion request into an incident.

**Reference** — Your Day 63 memory invalidation work.

---

### Day 168 — **[CONSOLIDATE]** Design portfolio review
**Concept (40 min)** — Six designs across very different constraint profiles. Extract the
patterns — what recurs, and what varies with which constraint.

**Practical (80 min)** — Write `designs/PATTERNS.md`: the recurring decisions and the
constraint that determines each one. Spaced review: Days 157 and 160.

**Proof of understanding** — Given a new AI system requirement, you can predict the major
architectural decisions from the constraints alone, before designing. That predictive ability
is what design fluency actually is.

**Reference** — Your six designs.

---

## Week 29 — Security

### Day 169 — Prompt injection: the taxonomy
**Concept (40 min)** — **Direct injection**: the user tells the model to ignore its
instructions. **Indirect injection**: instructions hidden in content the model reads — a web
page, a document, a log line, a tool result — which is far more dangerous because the victim
never sees it. **Exfiltration**: injected instructions cause the agent to send data somewhere
via a tool call, a markdown image URL, or a link. **Tool abuse**: injected instructions cause
the agent to invoke a legitimate tool destructively. The critical insight is that this is not
a filtering problem with a filtering solution — there is no reliable way to separate
instructions from data inside a single context.

**Practical (80 min)** — Build a red-team corpus of 30 injection cases targeting SENTINEL,
placed where SENTINEL actually reads: injected instructions in log lines, in a runbook, in a
code comment, in a trace attribute. Run them all and record what happens.

**Proof of understanding** — Report how many of the 30 succeeded in changing SENTINEL's
behaviour. It will be more than you expect, and log lines are an outstanding injection vector
precisely because they contain arbitrary user-controlled strings that nobody sanitises.

**Reference** — "Prompt Injection" (Simon Willison's writing on the topic); OWASP Top 10 for
LLM Applications, LLM01.

---

### Day 170 — The lethal trifecta and agent authorization
**Concept (40 min)** — The dangerous combination is: **access to private data**, **exposure to
untrusted content**, and **the ability to communicate externally**. Any agent with all three
can be made to exfiltrate. SENTINEL has all three by design — production telemetry, arbitrary
log content, and outbound tool calls. Since you cannot eliminate injection, you must remove
one leg of the trifecta or constrain what a compromised agent can accomplish. That is an
authorization problem: capability scoping, least privilege per step, and human approval as a
security control rather than a UX affordance.

**Practical (80 min)** — Design SENTINEL's permission model: which tools each agent role may
call, scoped to which resources, under which conditions. Implement it as an explicit policy
layer that every tool call passes through — not as prompt instructions, which are advisory at
best. Re-run the Day 169 red-team corpus against the enforced policy.

**Proof of understanding** — Report red-team success rate before and after policy enforcement.
Then state which leg of the trifecta you actually removed, and where SENTINEL still has all
three. Being precise about residual risk is the deliverable.

**Reference** — Simon Willison's "lethal trifecta" framing; capability-based security
literature.

---

### Day 171 — Sandboxing and egress control
**Concept (40 min)** — For agents that execute code or make network calls, containment is the
last line of defence and it must be enforced at the infrastructure layer. Network egress
allowlists (default deny), filesystem restrictions, resource limits, and a separate execution
identity with no ambient credentials. The classic failure is an agent sandbox with unrestricted
outbound network access — every other control is then decorative, because exfiltration only
needs one HTTP request.

**Practical (80 min)** — Harden Day 22's sandbox: default-deny egress with an explicit
allowlist, no credentials in the execution environment, filesystem read-only outside a scratch
directory, and enforced resource limits. Then attempt exfiltration from inside it through at
least five channels — direct HTTP, DNS, a markdown image URL rendered in the console, an error
message, and a tool call.

**Proof of understanding** — Report which of your five exfiltration attempts succeeded. The
markdown image URL rendered in your own console is the one that catches most people — the
agent never makes a request, the *browser* does.

**Reference** — OWASP LLM Top 10; container and network policy documentation.

---

### Day 172 — Supply chain: MCP servers and third-party tools
**Concept (40 min)** — Every MCP server you connect is code you did not write, receiving your
context and returning content the model trusts. The threat model includes a malicious server,
a compromised legitimate server, a server whose tool descriptions are crafted to shadow
another server's tools, and tool results engineered to redirect the agent. Provenance,
pinning, and treating all tool output as untrusted are the mitigations.

**Practical (80 min)** — Write `sentinel/SUPPLY-CHAIN.md`: every external dependency in
SENTINEL's tool path, its trust level, and what it could do if compromised. Implement tool
result sanitisation — treat every tool result as untrusted content with a clear delimiter and
an explicit instruction-hierarchy reminder (Day 9). Test with a deliberately hostile mock MCP
server you write yourself.

**Proof of understanding** — Demonstrate your hostile mock server attempting to redirect
SENTINEL, and show your sanitisation resisting it. Then state honestly whether sanitisation is
sufficient — it is a mitigation, not a solution, and pretending otherwise is how this goes
wrong.

**Reference** — MCP specification security considerations; your Day 28 trust analysis.

---

### Day 173 — **[BUILD]** SENTINEL v0.7 with audit and least privilege
**Concept (40 min)** — Integration, plus the audit trail. For a system with production access,
the audit log must be tamper-evident and must answer: what did the agent do, on whose
authority, on what evidence, and who approved it. That is a compliance requirement and an
incident-review requirement — and your Day 74 event log is already most of the way there.

**Practical (80 min)** — Assemble v0.7: policy-enforced tool scoping, hardened sandbox with
egress control, tool result sanitisation, multi-tenancy, and a tamper-evident audit trail
(hash-chained events) derived from your event log. Run the full replay suite to confirm
security controls did not break functionality. Run the red-team corpus. Tag `v0.7`.

**Proof of understanding** — Report the quality delta from adding security controls. Security
usually costs something — a guardrail false positive, a policy rejection of a legitimate call.
Quantify it rather than claiming it was free.

**Reference** — Your Day 74 event log; Day 117 guardrails.

---

### Day 174 — **[CONSOLIDATE]** Phase 7 review + publish
**Concept (40 min)** — The thesis: prompt injection has no filtering solution, so agent
security is an authorization and containment problem; an agent's permission model is an
architectural decision made on day one, not a hardening pass at the end.

**Practical (80 min)** — Draft deliverable #8: **"Threat modelling an agent with production
access."** Lead with the Day 169 red-team success rate and the Day 170 post-policy rate.
Include the exfiltration channel that surprised you and the honest statement of residual risk.
Spaced review: Days 169 and 171.

**Proof of understanding** — A reader can run your threat-modelling process against their own
agent and produce a permission model. Give them the method and the red-team corpus structure,
not a list of scary scenarios.

**Reference** — Your `notes/` from Days 157–173.

---

## Phase 7 exit checklist

- [ ] A reusable design template you can run under time pressure
- [ ] Five timed capacity estimation drills completed
- [ ] Six full system designs written, each critiqued and revised
- [ ] `designs/PATTERNS.md` mapping constraints to architectural decisions
- [ ] Multi-tenancy in SENTINEL with cross-tenant tests on every data path
- [ ] Data lifecycle with a deletion path covering derived data
- [ ] 30-case red-team injection corpus, success rate measured before and after policy
- [ ] Policy-enforced least-privilege tool scoping — enforced in code, not in prompts
- [ ] Sandbox with default-deny egress, tested against five exfiltration channels
- [ ] Supply chain document and tool result sanitisation, tested with a hostile mock server
- [ ] Tamper-evident audit trail answering what/who/why/approved-by
- [ ] Residual risk stated honestly
- [ ] SENTINEL v0.7 tagged
- [ ] Phase deliverable #8 drafted

**Next:** [Phase 8 — Harden & Ship](phase-08-harden-and-ship.md)
