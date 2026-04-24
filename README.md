# ⚡ ops-pilot

**AI agents that watch your CI/CD pipelines, diagnose failures, write the fix, and open a pull request — while your engineers sleep.**

> **Who this is for:** platform engineering teams running 10+ services on GitHub Actions / GitLab CI / Jenkins who are tired of the 2 AM CI page.

> Built by **[Adnan Khan](https://adnankhan.me)** · [LinkedIn](https://linkedin.com/in/passionateforinnovation)

[![Tests](https://img.shields.io/github/actions/workflow/status/adnanafik/ops-pilot/ops-pilot-self-test.yml?label=tests&style=flat-square)](https://github.com/adnanafik/ops-pilot/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

---

## 🎮 Live Demo

**[→ Try it now: adnanafik.github.io/ops-pilot](https://adnanafik.github.io/ops-pilot/)**

> Click a scenario, watch four AI agents light up in sequence, and see the generated PR and Slack message appear — no sign-up, no API key, runs entirely in your browser.

![ops-pilot demo](docs/demo.gif)

---

## What problem does this solve?

When a CI pipeline breaks at 2 AM, an engineer gets paged. They dig through logs, find the root cause, write a fix, open a PR, and notify the team. That cycle takes 30–90 minutes even for experienced engineers — and it's mostly mechanical work.

**ops-pilot automates the mechanical part:**

- 🔍 **Detects** the failure and pulls the relevant logs
- 🧠 **Diagnoses** the root cause using Claude (severity, affected service, confidence)
- 🔧 **Writes a fix**, commits it to a branch, and opens a draft PR for human review
- 📣 **Notifies** your team on Slack with a concise summary

Engineers still review and merge. ops-pilot handles the 2 AM triage.

---

## Quickstart

**Try the demo in 3 commands — no API key needed:**

```bash
git clone https://github.com/adnanafik/ops-pilot && cd ops-pilot
docker compose up ops-pilot-demo
open http://localhost:8000
```

**Run against your real pipelines (no local Python needed):**

```bash
cp .env.example .env        # add ANTHROPIC_API_KEY + GITHUB_TOKEN
# edit ops-pilot.yml — add your repos under pipelines:
docker compose --profile watcher run --rm ops-pilot-watcher \
  python3 scripts/watch_and_fix.py --once --dry-run   # triage only, no PRs opened
docker compose --profile watcher run --rm ops-pilot-watcher \
  python3 scripts/watch_and_fix.py --once              # full run — opens draft PRs
```

**Configure your repos in `ops-pilot.yml`:**

```yaml
anthropic_api_key: ${ANTHROPIC_API_KEY}
github_token: ${GITHUB_TOKEN}
slack_bot_token: ${SLACK_BOT_TOKEN}

pipelines:
  - repo: myorg/backend
    slack_channel: "#platform-alerts"
    severity_threshold: medium    # skip low-severity noise

  - repo: myorg/payments
    provider: gitlab_ci           # GitHub Actions, GitLab CI, or Jenkins
    slack_channel: "#payments-oncall"
    severity_threshold: high
```

---

## How it works

```mermaid
flowchart TB
    CI["💥 CI Failure\nGitHub · GitLab · Jenkins"] --> MON

    subgraph pipeline ["ops-pilot pipeline"]
        direction TB
        MON["👁 MonitorAgent\npolls every 30 s"]
        MON --> ROUTE["🔀 InvestigationRouter  · Phase 3\nfiles changed · diff size · log length"]

        subgraph triage ["Triage — fast or deep path  · Phase 3"]
            direction TB
            ROUTE -->|"simple failure\nsmall diff / short log"| FAST["🔍 TriageAgent\nfast path"]
            ROUTE -->|"complex failure\nlarge diff / rich log"| COORD["🧠 CoordinatorAgent\ndeep path"]
            subgraph workers ["Parallel specialist workers  · Phase 3"]
                direction LR
                WL["📋 LogWorker\nfetches log sections"]
                WS["📁 SourceWorker\nreads source files"]
                WD["🔍 DiffWorker\nreads full diff hunks"]
            end
            COORD <-->|"spawns via\nSpawnWorkerTool"| workers
        end

        FAST --> GATE{fix_confidence?}
        COORD --> GATE
        GATE -->|"HIGH / MEDIUM"| FIX["🔧 FixAgent\npatch + draft PR"]
        GATE -->|"LOW"| ESC["⚠️ EscalationSummary\nhuman review brief"]
        FIX --> NFIX["🔔 NotifyAgent\nfix-ready alert"]
        ESC --> NESC["🔔 NotifyAgent\nhuman-review alert"]
    end

    subgraph loop ["🔁 AgentLoop — shared execution engine  · Phases 1 & 2"]
        direction LR
        REG["ToolRegistry\nREAD_ONLY · WRITE\nREQUIRES_CONFIRMATION · DANGEROUS"]
        BUD["ContextBudget  · Phase 5\ntoken estimation · Strategy A compaction"]
    end

    FAST & COORD & workers & FIX -.->|"each runs via"| loop

    MEM["📚 MemoryStore  · Phase 4\nweighted similarity retrieval\nweekly consolidation job"]
    COORD -->|"retrieve similar\npast incidents"| MEM
    pipeline -.->|"save incident\npost-resolution"| MEM

    subgraph trust ["🔐 TrustContext  · Phase 7"]
        direction LR
        AUD["📋 AuditLog\none JSONL record per tool call\nper-day rotation · atomic writes"]
        EXP["💬 ExplanationGenerator\nLLM reasoning before\nREQUIRES_CONFIRMATION tools"]
    end

    loop -.->|"every tool call"| AUD
    loop -.->|"before write tools"| EXP

    subgraph tenancy ["🏢 TenantContext  · Phase 6"]
        direction LR
        TID["Identity\ntenant_id · actor"]
        PRM["PermissionsConfig\ntool allowlist"]
        RLM["RateLimiter\nsliding window"]
        UTK["UsageTracker\nAPI calls · tokens · incidents"]
    end

    tenancy -.->|"injected into every agent at startup"| pipeline

    LLM["☁️ LLM Backend\nAnthropic · AWS Bedrock · Google Vertex AI"]
    loop <-->|"complete_with_tools()\ncomplete()"| LLM
    ESC <-->|"generate_escalation_summary()"| LLM
    NFIX & NESC <-->|"generate Slack message"| LLM

    NFIX & NESC --> SLACK["📬 Slack / console"]
    FIX --> PR["🔀 Draft PR\nhuman reviews & merges"]
```

### The 30-second version

| Step | Agent | What it does |
|------|-------|-------------|
| 1 | **Monitor** | Polls GitHub Actions / GitLab CI / Jenkins every 30s. Finds new failed runs, fetches log output. |
| 2 | **Triage** | Runs an agentic tool-use loop: reads source files, fetches earlier log sections, diffs commits — until it has enough signal to conclude. Returns root cause, severity (LOW→CRITICAL), affected service, and fix confidence. |
| 3 | **Fix or Escalate** | If confidence is MEDIUM or HIGH: commits a patch and opens a draft PR. If confidence is LOW: generates an escalation summary (what was investigated, what was inconclusive, recommended next step) — no PR is opened; a human is required. |
| 4 | **Notify** | Posts a one-paragraph Slack summary: fix-ready alert with PR link, or escalation alert requesting human review. Falls back to console in dev mode. |

Every tool call (file reads, commits, PR opens) is written to a structured JSONL audit log. Destructive tools (`update_file`, `open_draft_pr`) get a pre-action LLM explanation generated before execution — observable without blocking.

**Deduplication:** ops-pilot uses open GitHub/GitLab PRs as its source of truth. If a PR for a commit already exists, it waits — it will never spam your repo with duplicate PRs, even after a crash or redeploy.

---

## Architecture

Four agents (Monitor → Triage → Fix → Notify), each extending `BaseAgent[OutputT]` and running on a generic `AgentLoop` that handles tool-use iteration. Agents communicate via Pydantic models — no raw dicts cross boundaries. Tools are permission-tiered: READ_ONLY → WRITE → REQUIRES_CONFIRMATION, enforced by `ToolRegistry`. Memory, context budgeting, trust (audit log + pre-action explanation), and multi-tenancy are isolated modules in `shared/`.

→ **[Full architecture](docs/ARCHITECTURE.md)** · **[Why these design decisions?](docs/DESIGN.md)**

---

## LLM backends

ops-pilot works with any of the three — switch by changing one config line:

| Backend | Config | Auth |
|---------|--------|------|
| **Anthropic API** (default) | `llm_provider: anthropic` | `ANTHROPIC_API_KEY` |
| **AWS Bedrock** | `llm_provider: bedrock` | IAM role / `AWS_ACCESS_KEY_ID` |
| **Google Vertex AI** | `llm_provider: vertex_ai` | ADC / `GOOGLE_APPLICATION_CREDENTIALS` |

```yaml
# Switch to Bedrock — no agent code changes needed
llm_provider: bedrock
aws_region: us-east-1
model: anthropic.claude-sonnet-4-5-20251001-v1:0
```

---

## Claude Code integration

ops-pilot ships with 5 slash commands for [Claude Code](https://claude.ai/code) in `.claude/commands/`. Open this repo in Claude Code and use them directly — each one reads the actual source files before acting, so it follows the project's exact patterns.

```bash
# Diagnose a CI failure from log output or a description
/triage "auth service null pointer on commit a3f21b7"

# Add a new pipeline — detects provider, validates config, runs Python to confirm
/add-pipeline myorg/my-service provider:github_actions

# Scaffold a full CIProvider implementation (factory + __init__ wired automatically)
/new-provider CircleCI

# Run the watcher — checks .env, shows configured pipelines, then starts
/run once --dry-run

# Generate a new demo scenario JSON from a failure description
/scenario "Redis connection timeout in payment service"
```

Every command is defined in `.claude/commands/<name>.md` — edit the `.md` file to change how Claude approaches the task.

---

## How is this different from…

| | ops-pilot | Sweep | Copilot Workspace | Sentry Autofix | Aider |
|---|---|---|---|---|---|
| **Triggered by** | CI failure (autonomous) | Human-filed GitHub issue | Human opens a task | Production exception | Human CLI prompt |
| **Scope** | CI pipeline failures only | Any feature/bug | Any coding task | Runtime errors | Any code change |
| **Produces** | Triage + draft PR + Slack alert | Draft PR | PR | Patch suggestion in Sentry UI | Local diff |
| **Observability** | JSONL audit log + pre-action LLM explanation | — | GitHub-native | Sentry-native | — |

---

## Related

**[retro-pilot](https://github.com/adnanafik/retro-pilot)** — autonomous post-mortem generator.
ops-pilot catches the failure and opens a PR. retro-pilot takes the resolved incident and produces a structured post-mortem stored in a searchable knowledge base.

---

## Running tests

No local Python install required — runs inside Docker:

```bash
docker compose run --rm test                  # 335 tests
docker compose run --rm test pytest -k triage # single agent
docker compose run --rm test ruff check agents/ shared/
```

Or locally if you have Python 3.11+:

```bash
pip install -e ".[dev]"
pytest
```

---

## About the author

Adnan Khan builds AI systems for platform engineering teams. [LinkedIn](https://linkedin.com/in/passionateforinnovation) · [adnankhan.me](https://adnankhan.me)

---

## License

MIT © 2026 Adnan Khan
