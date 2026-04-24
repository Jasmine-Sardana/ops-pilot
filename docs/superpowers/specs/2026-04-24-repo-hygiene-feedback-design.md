# Repo Hygiene Feedback — Design

**Date:** 2026-04-24
**Scope:** Nine of ten feedback items for the ops-pilot and retro-pilot GitHub repositories. Item 8 (PyPI publishing) is deferred to its own design.
**Goal:** Convert two well-architected repos into repos that *read* as production-ready to engineers evaluating them for adoption.

---

## Motivation

Reviewer feedback identified ten items hurting adoption signals across both repos. They fall into three classes:

1. **Credibility tells** — phrases, layouts, or missing pieces that make the project look like a personal experiment rather than something you'd depend on. (Items 1, 10.)
2. **Above-the-fold friction** — content structure that makes a skimmer bounce before they reach the value prop. (Items 2, 3.)
3. **Missing adoption scaffolding** — things most OSS projects skip but that compound over time (comparison to alternatives, cross-linking, metadata, contribution onramps). (Items 4, 5, 6, 7, 9.)

The fix is not more code. It is removing phrases that signal "unmaintained," relocating walls of text below the hook, and adding the standard OSS infrastructure most projects never bother with.

---

## Scope

**In scope (this spec):** items 1, 2, 3, 4, 5, 6, 7, 9, 10 across both repos.

**Out of scope:** item 8 (PyPI publishing). That needs its own design — versioning strategy, GitHub Actions release workflow, PyPI account/2FA setup, wheel vs. sdist decisions, `pip install` quickstart integration in both READMEs. Revisit after this spec's work lands.

---

## Approach

Two parallel workstreams, one per repo, sharing this design doc. Each logical change is its own commit so any piece can be reverted independently.

**Dependency ordering:** on ops-pilot, the README restructure (item 2) must land before the comparison table (item 4) is added, so the new section is inserted into the post-restructure README.

**Before/after principle:** every change is additive or redistributive. No existing content is deleted except the "portfolio project" phrase (item 1) and the top-byline title (item 10). The Architecture file tree and Design decisions content are *relocated*, not removed.

---

## Per-item design

### Item 1 — Fix the license line (ops-pilot only)

**Current:** `MIT © 2026 — built as a portfolio project demonstrating production-quality multi-agent AI systems.`

**New:** `MIT © 2026 Adnan Khan`

The phrase "portfolio project" reads as "not maintained, do not depend on this." Depth of the README already signals seriousness; the license line should be a simple attribution.

### Item 2 — Restructure ops-pilot README (biggest single lever)

The current README is 437 lines. The Architecture section (lines 166-247) is 80 lines of file tree, and the Design decisions section (lines 295-413) is ~120 lines of prose. Both compete with the hook above the fold.

**Relocation:**
- Move the full file tree (current lines 168-245) + closing paragraph to `docs/ARCHITECTURE.md`.
- Move all 14 "Why X" sections (current lines 295-413) to `docs/DESIGN.md`.
- Each new doc gets a short intro paragraph and a "← Back to README" link at the top.

**README replacement for Architecture section:**

```markdown
## Architecture

Four agents (Monitor → Triage → Fix → Notify), each extending `BaseAgent[OutputT]` and running on a generic `AgentLoop` that handles tool-use iteration. Agents communicate via Pydantic models — no raw dicts cross boundaries. Tools are permission-tiered: READ_ONLY → WRITE → REQUIRES_CONFIRMATION, enforced by `ToolRegistry`. Memory, context budgeting, trust (audit log + pre-action explanation), and multi-tenancy are isolated modules in `shared/`.

→ **[Full architecture](docs/ARCHITECTURE.md)** · **[Why these design decisions?](docs/DESIGN.md)**
```

**Final ops-pilot README section order** (after all edits):

1. Title / byline / badges
2. Live Demo
3. What problem does this solve?
4. Quickstart
5. How it works (Mermaid + 30-second table)
6. Architecture *(5-line summary + links)*
7. LLM backends
8. Claude Code integration
9. **How is this different from…** *(new — item 4)*
10. **Related** *(new — item 7)*
11. Running tests
12. **About the author** *(new — item 10)*
13. License *(fixed — item 1)*

### Item 3 — "Who this is for" line (both repos)

Placed directly after the hook line (the `**AI agents that…**` / `> ops-pilot catches the failure…` opening).

**ops-pilot:**
> **Who this is for:** platform engineering teams running 10+ services on GitHub Actions / GitLab CI / Jenkins who are tired of the 2 AM CI page.

**retro-pilot:**
> **Who this is for:** platform and SRE teams that want every resolved incident to produce a structured post-mortem — without the on-call engineer having to write one from scratch.

### Item 4 — "How is this different from…" comparison tables (both repos)

Tables only, no "angle" prose beneath. Reader can draw their own conclusion.

#### ops-pilot

Placed after "Claude Code integration," before "Related."

```markdown
## How is this different from…

| | ops-pilot | Sweep | Copilot Workspace | Sentry Autofix | Aider |
|---|---|---|---|---|---|
| **Triggered by** | CI failure (autonomous) | Human-filed GitHub issue | Human opens a task | Production exception | Human CLI prompt |
| **Scope** | CI pipeline failures only | Any feature/bug | Any coding task | Runtime errors | Any code change |
| **Produces** | Triage + draft PR + Slack alert | Draft PR | PR | Patch suggestion in Sentry UI | Local diff |
| **Observability** | JSONL audit log + pre-action LLM explanation | — | GitHub-native | Sentry-native | — |
```

#### retro-pilot

Placed *below* the existing "How it's different from ops-pilot" section (which stays — it serves a different reader: the one figuring out the two-project pair). The new section is titled to distinguish purpose:

```markdown
## How it compares to alternatives

| | retro-pilot | Blameless | incident.io | FireHydrant | Rootly |
|---|---|---|---|---|---|
| **Category** | Autonomous agent (single-purpose) | IM platform | IM platform | IM platform | IM platform |
| **Post-mortem** | Fully generated from evidence | Human-authored with AI help | Human-authored with AI help | Template-driven | Template-driven |
| **Evidence collection** | Automatic (Log / Metrics / Git / Slack workers) | Manual + integrations | Manual + integrations | Manual + integrations | Manual + integrations |
| **Evaluation** | LLM-as-judge, 3-cycle revision loop | Human review | Human review | Human review | Human review |
```

**Verification caveat:** these tables are drafted from general knowledge of those tools as of 2026-Q1. Competitor AI features move fast — confirm accuracy before PR merge.

### Item 5 — retro-pilot badges

Match ops-pilot's badge set. Place directly under the byline:

```markdown
[![Tests](https://img.shields.io/github/actions/workflow/status/adnanafik/retro-pilot/retro-pilot-ci.yml?label=tests&style=flat-square)](https://github.com/adnanafik/retro-pilot/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
```

Test workflow filename confirmed: `retro-pilot-ci.yml`.

### Item 6 — GitHub repo metadata

**ops-pilot (already 80% set):**
- Description: ✓ already set, no change
- Homepage: ✓ already `https://adnanafik.github.io/ops-pilot/`, no change
- Topics: add `multi-agent`, `python` to existing list. Final set: `ai-agents`, `anthropic`, `cicd`, `devops`, `incident-response`, `llm`, `multi-agent`, `platform-engineering`, `python`, `sre`

**retro-pilot (needs full fill-in):**
- Description: ✓ already set, no change
- Homepage: set to `https://adnanafik.github.io/retro-pilot/`
- Topics: set to `ai-agents`, `anthropic`, `chromadb`, `incident-management`, `llm`, `multi-agent`, `post-mortem`, `python`, `sre`

All done via `gh api repos/<owner>/<repo> -X PATCH -f homepage=... -F topics[]=...`. Exact commands will be shown before execution (since these are externally visible mutations).

### Item 7 — "Related" section on ops-pilot (cross-link)

Placed before "Running tests":

```markdown
## Related

**[retro-pilot](https://github.com/adnanafik/retro-pilot)** — autonomous post-mortem generator.
ops-pilot catches the failure and opens a PR. retro-pilot takes the resolved incident and produces a structured post-mortem stored in a searchable knowledge base.
```

retro-pilot already cross-links to ops-pilot (line 11 of its README). No change there.

### Item 9 — CONTRIBUTING.md + good-first-issue labels

**Part A — CONTRIBUTING.md (both repos).** Same skeleton, repo-specific bits swapped:

```markdown
# Contributing to <repo>

Thanks for considering a contribution.

## Getting started
1. Fork and clone.
2. `pip install -e ".[dev]"` (Python 3.11+).
3. `docker compose run --rm test` to run the suite.

## Finding something to work on
- Check [good first issues](https://github.com/adnanafik/<repo>/labels/good%20first%20issue) if you're new.
- For larger changes, open an issue first to align on scope.

## Code style
- Type hints everywhere, no `Any`.
- `ruff check .` must pass.
- pytest coverage ≥ <threshold> on agent logic.

## Pull requests
- One logical change per PR.
- Add or update tests.
- Short imperative commit subjects.
```

Thresholds: ops-pilot = 80%, retro-pilot = 85% (from each project's CLAUDE.md).

**Part B — Good-first-issue labels.** Both repos have zero open issues, so nothing to label until issues exist. Candidate issues (user approves the ones to file):

**ops-pilot candidates (5):**
1. Add a CircleCI provider (pattern established by `providers/github.py`, `providers/gitlab.py`, `providers/jenkins.py`; there's a `/new-provider` slash command to scaffold).
2. Add a new demo scenario to `demo/scenarios/` (schema documented, `/scenario` slash command exists).
3. Improve the error message when `ANTHROPIC_API_KEY` is unset — currently cryptic; should point to setup docs.
4. Add a `--verbose` flag to `scripts/watch_and_fix.py` for debug logging.
5. Add a deployment guide for Fly.io or Railway (docs addition, low risk).

**retro-pilot candidates (5):**
1. Add a JiraWorker evidence collector (pattern from existing Log / Metrics / Git / Slack workers).
2. Add a new demo scenario to `demo/scenarios/`.
3. Add a `scripts/list_postmortems.py` CLI that lists stored post-mortems with filters.
4. Export a post-mortem to a plain Markdown file.
5. Add a PagerDutyWorker evidence collector (same pattern as Jira).

For each approved candidate: create the issue via `gh issue create`, apply the `good first issue` label (create the label if it doesn't exist in the repo).

### Item 10 — Byline treatment (both repos)

**New top byline** (replaces the current one in both repos):

```markdown
> Built by **[Adnan Khan](https://adnankhan.me)** · [LinkedIn](https://linkedin.com/in/passionateforinnovation)
```

Three things changing:
1. Title dropped from top byline.
2. "Portfolio" chip dropped — the name already links to adnankhan.me, so "Portfolio" was redundant.
3. **Format normalized to blockquote on both repos.** ops-pilot already uses blockquote; retro-pilot currently uses bare bold (`**Built by...**` without `>`) — this change converts it to blockquote to match.

**New "About the author" section** (bottom of README, before License, both repos):

```markdown
## About the author

Adnan Khan builds AI systems for platform engineering teams. [LinkedIn](https://linkedin.com/in/passionateforinnovation) · [adnankhan.me](https://adnankhan.me)
```

Action-oriented phrasing (not employer-specific). Describes what I do rather than what job I hold.

---

## Commit plan

### ops-pilot (9 commits)

1. `docs: remove "portfolio project" phrase from license line` (item 1)
2. `docs: add "Who this is for" line to README hook` (item 3)
3. `docs: extract Architecture and Design decisions into separate docs` (item 2)
4. `docs: add "How is this different from…" comparison table` (item 4)
5. `docs: add Related section cross-linking retro-pilot` (item 7)
6. `docs: move author title to About the author section` (item 10)
7. `docs: add CONTRIBUTING.md` (item 9 part A)
8. `chore: add multi-agent and python topics to GitHub metadata` (item 6) — *via `gh api`, not a git commit*
9. `chore: open good-first-issue candidates` (item 9 part B) — *via `gh issue create`, not a git commit*

### retro-pilot (5 commits)

1. `docs: add Tests / Python / License badges` (item 5)
2. `docs: add "Who this is for" line to README hook` (item 3)
3. `docs: add "How it compares to alternatives" section` (item 4)
4. `docs: move author title to About the author section; add CONTRIBUTING.md` (items 10 + 9A batched — both small doc changes)
5. `chore: set homepage and topics on GitHub` (item 6) + `chore: open good-first-issue candidates` (item 9 part B) — *both via `gh`, not git commits*

---

## Verification

Each commit is independently reviewable on GitHub. Overall checks after the work lands:

- **Rendered READMEs** — skim both repos' `main` branch READMEs on github.com. Check that the hook is visible above the fold without scrolling past a wall of text.
- **Badges render** — green badges appear on retro-pilot.
- **Cross-links work** — clicking "retro-pilot" on ops-pilot's README arrives at the retro-pilot README, and vice versa.
- **docs/ARCHITECTURE.md + docs/DESIGN.md render on github.com** — code blocks, links back to README work.
- **Repo metadata** — `gh api repos/adnanafik/<repo>` shows correct topics and homepage.
- **Good-first-issues** — both repos appear in GitHub's [good first issues finder](https://github.com/topics/good-first-issue) once labels are applied.

---

## Open approvals needed during implementation

1. **Comparison table accuracy (item 4):** confirm before merging PR — competitor AI features may have shifted.
2. **Good-first-issue candidates (item 9):** user approves which of the 5 per repo to actually file.
3. **GitHub metadata mutations (item 6):** exact `gh api` commands shown and approved before running (externally visible).
