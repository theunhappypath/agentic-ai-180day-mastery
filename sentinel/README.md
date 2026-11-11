# SENTINEL — the capstone

An agentic incident response platform. Full spec: [docs/capstone-sentinel.md](../docs/capstone-sentinel.md).

| Directory | Holds | First populated |
|---|---|---|
| `agent/` | Agent loop, tools, MCP server, approval gate, orchestration | Phase 1 (v0.1) |
| `corpus/` | Seeded incident corpus — logs, traces, deploys, runbooks | Phase 1 |
| `retrieval/` | Indexes, chunking, rerankers, retrieval eval set | Phase 2 (v0.2) |
| `evals/` | Golden sets, judges, replay harness, CI gate | Phase 4 (v0.4) |
| `serving/` | vLLM configs, router, load and latency benchmarks | Phase 5 (v0.5) |
| `ui/` | Next.js console — watch the agent, approve gates, read traces | Phase 1, Day 35 |

Empty directories carry a `.gitkeep` until their phase arrives.
