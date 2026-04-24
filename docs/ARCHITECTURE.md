# ops-pilot Architecture

Detailed structure of the ops-pilot codebase. For a high-level summary, see the [README](../README.md#architecture). For the reasoning behind these choices, see [DESIGN.md](DESIGN.md).

← [Back to README](../README.md)

---

## File structure

```
ops-pilot/
├── agents/
│   ├── base_agent.py           ← Abstract base: run(), describe(), injected LLM backend
│   ├── monitor_agent.py        ← Polls CI provider; returns Failure models
│   ├── triage_agent.py         ← Fast path: single agentic loop; returns Triage
│   ├── coordinator_agent.py    ← Deep path: spawns parallel workers; returns Triage
│   ├── investigation_router.py ← Routes failures to fast or deep path (heuristic)
│   ├── fix_agent.py            ← LLM patch generation + PR via CI provider
│   ├── notify_agent.py         ← Slack / webhook / console notification
│   └── tools/
│       ├── triage_tools.py     ← GetFileTool, GetMoreLogTool, GetCommitDiffTool (READ_ONLY)
│       ├── fix_tools.py        ← GetRepoTreeTool, CreateBranchTool (WRITE); UpdateFileTool, OpenDraftPRTool (REQUIRES_CONFIRMATION)
│       └── coordinator_tools.py ← SpawnWorkerTool + LogWorker / SourceWorker / DiffWorker
├── providers/
│   ├── base.py              ← CIProvider ABC (7 methods: get_failures, open_draft_pr, …)
│   ├── github.py            ← GitHub Actions implementation
│   ├── gitlab.py            ← GitLab CI implementation
│   ├── jenkins.py           ← Jenkins implementation (delegates git ops to GitHub/GitLab)
│   └── factory.py           ← make_provider(pipeline, cfg) — wires config to provider
├── shared/
│   ├── models.py            ← Pydantic models: Failure → Triage → Fix → Alert → MemoryRecord
│   ├── agent_loop.py        ← Generic AgentLoop[T]: tool-use loop + Tool ABC + ToolContext + confirm hook
│   ├── tool_registry.py     ← ToolRegistry: permission-tier watermark (READ_ONLY ≤ WRITE ≤ DANGEROUS ≤ REQUIRES_CONFIRMATION)
│   ├── context_budget.py    ← ContextBudget: token estimation + Strategy A compaction
│   ├── memory_store.py      ← MemoryStore: append + weighted similarity retrieval (no external deps)
│   ├── config.py            ← YAML config + env-var substitution + Pydantic validation (TrustConfig, RateLimitsConfig, PermissionsConfig)
│   ├── llm_backend.py       ← LLMBackend Protocol + Anthropic / Bedrock / Vertex backends
│   ├── task_queue.py        ← File-locked task queue (atomic rename, no broker needed)
│   ├── state_store.py       ← JSON state (dedup across restarts)
│   ├── tenant_context.py    ← TenantContext: per-deployment identity, usage tracker, tool permissions
│   ├── rate_limiter.py      ← RateLimiter: sliding-window API call + token limits per tenant
│   ├── usage_tracker.py     ← UsageTracker: per-tenant API call / token / incident counters
│   ├── audit_log.py         ← AuditLog: one JSONL record per tool call, per-day rotation, atomic writes
│   ├── explanation_gen.py   ← ExplanationGenerator: pre-action LLM explanation for REQUIRES_CONFIRMATION tools
│   ├── escalation.py        ← EscalationSummary + generate_escalation_summary (LOW-confidence path)
│   └── trust_context.py     ← TrustContext dataclass + make_trust_context factory
├── demo/
│   ├── app.py               ← FastAPI SSE server for local demo
│   ├── scenarios/           ← 3 pre-recorded realistic failure scenarios (JSON)
│   └── static/index.html    ← Single-file demo UI — vanilla JS, no build step
├── docs/
│   ├── index.html           ← GitHub Pages static demo (no server, pure JS)
│   ├── demo.gif             ← Animated walkthrough embedded in README
│   └── scenarios/           ← Scenario JSON files served statically
├── tests/
│   ├── conftest.py                 ← Shared fixtures (sample_failure, mock_backend, …)
│   ├── test_triage_agent.py
│   ├── test_coordinator_agent.py
│   ├── test_investigation_router.py
│   ├── test_memory_store.py
│   ├── test_fix_agent.py
│   ├── test_fix_tools.py
│   ├── test_notify_agent.py
│   ├── test_monitor_agent.py
│   ├── test_llm_client.py
│   ├── test_state_store.py
│   ├── test_task_queue.py
│   ├── test_agent_loop.py          ← AgentLoop + TrustContext integration tests
│   ├── test_audit_log.py
│   ├── test_explanation_gen.py
│   ├── test_escalation.py
│   ├── test_trust_context.py
│   ├── test_tenant_context.py
│   ├── test_rate_limiter.py
│   └── fixtures/                   ← Sample CI log files
├── .claude/commands/        ← 5 Claude Code slash commands (see below)
├── memory/                  ← Incident memory (created at runtime)
│   ├── incidents/           ← One JSON file per incident
│   └── index.json           ← Scoring metadata for similarity retrieval
├── scripts/
│   ├── watch_and_fix.py     ← Production entry point (continuous watcher)
│   └── consolidate_memory.py ← Weekly job: extract durable fix patterns from incident groups
├── run_pipeline.py          ← One-shot live runner for manual testing
├── ops-pilot.example.yml    ← Fully documented config template
├── Dockerfile
└── docker-compose.yml       ← demo UI + optional watcher service
```

Every agent communicates exclusively through typed Pydantic models — no raw dicts cross boundaries. Every agent is independently testable with a mock backend.
