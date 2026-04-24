# Design Decisions

The reasoning behind ops-pilot's architecture. Each section answers a "why did you choose X over Y?" question that a reviewer or customer might raise.

← [Back to README](../README.md) · [Architecture reference](ARCHITECTURE.md)

---

### Why four separate agents instead of one big prompt?

Each agent has one job, one input type, and one output type. TriageAgent can be tested in isolation with a mock backend. FixAgent can be swapped for a different patching strategy. The pipeline is composable — you can run Triage-only (`--dry-run`) without touching the Fix or Notify agents.

### Why file-based task locking?

The task queue uses `os.rename()` for atomic task claiming — a POSIX guarantee that means two workers can never claim the same task without a database or message broker. Zero external dependencies, git-friendly, deployable anywhere. Pattern from the [Anthropic multi-agent systems article](https://www.anthropic.com/research/building-effective-agents).

### Why simulation mode?

Live agentic demos are brittle: API rate limits, flaky network, non-deterministic LLM output. Pre-recorded scenarios replay realistic runs with SSE streaming — the demo always works, loads instantly, and costs nothing to host on GitHub Pages.

### Why a tool-use loop in Triage instead of a single prompt?

The original TriageAgent sent one prompt and hoped the answer was in the last 50 log lines. Real failures often aren't: the root cause is 100 lines above the tail, in the source file at the failing line, or in the actual diff hunks (not a summary of which files changed).

`AgentLoop` lets the model request exactly what it needs — `get_file`, `get_more_log`, `get_commit_diff` — and stop when it has enough signal. If it hits the turn limit before concluding, it escalates with partial findings rather than opening a PR based on a guess. A wrong fix is more expensive than a missed fix: it creates a PR engineers have to triage, and it erodes trust in the system.

### Why a router instead of one agent that decides its own strategy?

The routing decision (fast vs. deep) is now a visible, logged record: "this failure was routed to deep investigation because 4 files changed." If it's hidden inside an agent's system prompt, engineers can't inspect or tune it without reading LLM outputs.

`InvestigationRouter` routes heuristically (file count, diff size, log length) in Phase 3. In Phase 4, it can be upgraded to LLM-based classification backed by incident memory — the interface (`route() → 'fast' | 'deep'`) stays the same.

### Why are coordinator workers isolated from each other?

Each worker (`log_worker`, `source_worker`, `diff_worker`) runs in its own `AgentLoop` with its own message history and a scoped tool list. `log_worker` cannot read source files; `diff_worker` cannot fetch logs. Two benefits: (1) workers stay focused and don't spend their context budget on tangents; (2) the coordinator sees only clean summaries, not raw tool output from 9 concurrent tool calls.

Workers cannot spawn further workers — no `SpawnWorkerTool` in their tool list. This prevents unbounded recursion and keeps the depth predictable.

### Why a tool registry instead of passing tool lists directly?

`TriageAgent` used to hardcode `[GetFileTool(), GetMoreLogTool(), GetCommitDiffTool()]`. That worked, but the safety guarantee ("triage never gets write tools") lived only in the developer's head.

`ToolRegistry.get_tools(max_permission=READ_ONLY)` makes the blast-radius ceiling structural — TriageAgent declares its ceiling at construction time and the registry enforces it. Adding a new write tool to the catalog doesn't automatically make it available to triage; the agent has to explicitly raise its ceiling. `REQUIRES_CONFIRMATION` tools are excluded from all watermark queries and additionally gated at execution time by a `confirm` hook — no hook wired means the tool is always denied (fail-safe, not fail-open).

### Why structured weighted similarity instead of embeddings?

Embedding-based similarity requires either an external API (Anthropic has no embeddings endpoint) or a heavy dependency like `sentence-transformers` (adds PyTorch to the image). Both break the "zero broker" story.

The alternative — structured weighted similarity over typed Triage fields — is actually better for this domain:

```
score = (
    1.0 × exact_match(failure_type)     # "pytest / test-auth" is high-signal
    + 0.6 × exact_match(affected_service) # same service = same codebase area
    + 0.4 × token_jaccard(root_cause)    # similar error vocabulary
) / 2.0   → normalized [0, 1]
```

When a customer asks "why did it pull that old incident?", you can point at the weights rather than explaining a vector space. Root cause tokens are precomputed at write time — query-time is a tight loop with no LLM calls, no IDF corpus, no external deps.

The tradeoff: no semantic similarity ("OOM killed" vs "heap exhaustion"). At ops-pilot scale — hundreds of incidents, constrained vocabulary — token overlap performs close to embeddings in practice.

### Why does memory retrieval live in CoordinatorAgent, not InvestigationRouter?

Memory retrieval before a fast-path triage would be wasted: simple failures don't need historical context. Deep investigations do.

The coordinator already decides what workers to spawn and what brief to give them. Retrieving prior incidents before spawning lets that context flow into both the spawning decision and the task brief passed to each worker. The retrieval is also visible in the coordinator's initial message — auditable in Phase 7's structured log, not hidden in a system prompt.

### Why does `ContextBudget` live outside `AgentLoop`, and why is it opt-in?

`AgentLoop` is a generic execution engine — it shouldn't know what model it's running on or what its context limit is. Those are operational concerns owned by the entry point that constructs the agents. `ContextBudget` is injected at construction time; `AgentLoop` just calls `should_compact` and `compact` without knowing how either works.

`context_budget=None` means "no budgeting" — existing call sites (tests, demo mode) are unchanged. New operational deployments in `watch_and_fix.py` wire in a budget sized for the model in use. The pattern is the same as `memory_store` on `CoordinatorAgent`: capabilities are opt-in, not forced on every caller.

### Why `chars // 4` and not the Anthropic token-counting API?

Token counting is for triggering a compaction decision, not for billing. The heuristic `len(all_chars) // 4` is conservative — it tends to underestimate for code and log content — so triggering at 75% of the limit absorbs the error. The Anthropic counting endpoint adds a network round-trip before every inference call, which is the wrong trade on an already-hot path. More importantly, adding a counting method to `LLMBackend` would force all three backends (Anthropic, Bedrock, Vertex) and all test mocks to implement it — a maintenance tax for an internal loop concern.

### Why Strategy A (replace tool_result bodies) and not full-history summarization?

By the time compaction triggers, the model has already interpreted each tool result in its subsequent assistant turn. The interpretation is load-bearing; the raw source data isn't:

```
turn N:   tool_result  → [200 lines of raw CI log]
turn N+1: assistant    → "NPE at TokenService.validate() line 42"
```

Replacing the raw log with a stub loses nothing the model doesn't already have. Full-history summarization (Strategy B) would cost an extra LLM call on a context-stressed path, and the model summarizing its own reasoning can drop details that become relevant two turns later. Strategy B can slot in later by implementing the same `compact()` interface — the architecture supports it without changing `AgentLoop`.

### Why per-deployment isolation instead of a runtime tenant switcher?

`TenantContext` is constructed once at startup from the config file and injected into every agent. This means the deployment model is "one config file = one customer" — isolated processes, isolated state, isolated usage tracking. A bug in Customer A's pipeline cannot reach Customer B's memory or rate limit counters.

The alternative — a shared process with a `tenant_id` routing key — would require every data store (memory, state, audit log) to be partitioned by tenant ID, and every agent to filter carefully. One missed filter = data leak. For an agentic system that writes files and opens PRs, the blast radius of a data-routing mistake is unacceptably high. Process isolation is boring and correct.

### Why is `RateLimiter` a sliding window, not a fixed bucket?

A fixed 1-hour bucket resets on the clock: a deployment could use its entire hourly quota in the last 10 minutes of the hour, then the full quota again in the first 10 minutes of the next — 200% in 20 minutes with no rate limit applied. A sliding window (per-call timestamps in a deque) means "at most N calls in any 60-minute window," which is what operators actually want when they say "1000 calls per hour."

### Why a structured JSONL audit log instead of application logs?

Application logs are for debugging; audit logs are for accountability. The difference: application logs are prose consumed by developers after a crash. Audit logs are structured records consumed by compliance tooling, dashboards, and incident reviewers after a breach or unexpected action.

JSONL (one JSON object per line) makes the audit trail grep-friendly and ingestible by any log pipeline (CloudWatch, Datadog, Splunk) without a parser. Rotating by day (`audit/YYYY-MM-DD.jsonl`) bounds file size and maps naturally to retention policies ("keep 90 days"). Atomic writes (`mkstemp` + `rename`) prevent partial records if the process dies mid-write.

### Why does `REQUIRES_CONFIRMATION` auto-proceed when `TrustContext` is present?

Phase 7 is an *observability layer*, not an approval gate. The pre-action explanation is generated so that the audit log contains a human-readable record of *why* the agent decided to commit a file or open a PR — not to block the action waiting for a human click.

Blocking confirmation (`Phase 8`) changes the system from "AI takes action, humans can audit" to "AI proposes action, human approves before execution." That's a fundamentally different product (and deployment model). Phase 7 establishes the explanation infrastructure that Phase 8 will reuse — the `confirm` hook in `AgentLoop` is already the extension point for that upgrade.

### Why generate an escalation summary instead of returning LOW-confidence triage directly?

A LOW-confidence `Triage` says "I'm not sure." An `EscalationSummary` says "here's what I investigated, here's what I couldn't pin down, and here's what you should do next." That's the difference between an alert that pages an engineer at 2 AM and makes them dig through the same evidence the agent already processed, versus an alert that hands off a structured investigation brief.

The escalation summary is also what gets sent to Slack — engineers see a purpose-built "human review required" message, not a raw Triage object with `fix_confidence: LOW` that requires them to know what that field means.

### Why draft PRs, not auto-merge?

ops-pilot is a force multiplier, not a replacement for engineering judgment. It opens the PR, writes the description, and notifies the team. A human reviews the diff and merges. This keeps the system useful without making it dangerous.

### Why Pydantic models between agents?

Raw dicts break silently when a key is missing. Pydantic validates at construction time, generates JSON Schema for tool-use prompts, and makes the data contract between agents explicit and type-checked.
