# Repo Hygiene Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply nine of ten reviewer feedback items across the ops-pilot and retro-pilot repos — README edits, new docs, CONTRIBUTING.md, GitHub metadata, and good-first-issue candidates. Item 8 (PyPI) is out of scope.

**Architecture:** Markdown-only work plus `gh` CLI calls. One commit per logical change so each piece is independently revertable. Line numbers in the spec become unstable as earlier tasks shift the file, so this plan anchors edits to unique string markers (section headings, distinctive phrases) rather than line numbers.

**Tech Stack:** Markdown, `gh` CLI, git. No Python or tests involved — this is doc work.

**Source spec:** `ops-pilot/docs/superpowers/specs/2026-04-24-repo-hygiene-feedback-design.md` (commit `ee7d7b9`).

---

## File Structure

### Files to create

| Path | Responsibility |
|---|---|
| `ops-pilot/docs/ARCHITECTURE.md` | Full file tree + "every agent communicates…" paragraph, relocated from README |
| `ops-pilot/docs/DESIGN.md` | 14 "Why X" design-decision sections, relocated from README |
| `ops-pilot/CONTRIBUTING.md` | Short contributor onramp |
| `retro-pilot/CONTRIBUTING.md` | Short contributor onramp (same template) |

### Files to modify

| Path | What changes |
|---|---|
| `ops-pilot/README.md` | License line, Who-this-is-for line, Architecture section replacement, new comparison / Related / About sections, byline edit |
| `retro-pilot/README.md` | Badges, Who-this-is-for line, new comparison section, byline edit, About section |

### External (non-file) mutations

| Target | Via |
|---|---|
| GitHub repo metadata (topics, homepage) | `gh api repos/... -X PATCH` |
| Good-first-issue label + candidate issues | `gh label create`, `gh issue create` |

---

## Working Directory Notes

Each task states its `cwd`. Two roots:

- `OP=/Users/adnankhan/dev/ops-pilot`
- `RP=/Users/adnankhan/dev/retro-pilot`

Tasks that run `git` commands must be executed from the correct repo root — don't rely on a previous task's `cd`.

---

## Ordering & Dependencies

Tasks 1-9 operate on ops-pilot, tasks 10-14 on retro-pilot. Order is deliberate:

- **Task 3 (restructure) must run before Task 4** on ops-pilot — Task 4 adds a new section at a position that only exists after restructure.
- **All other ops-pilot tasks are independent** but run in the spec's order because commits stack cleanly that way.
- **Tasks 8, 9, 14 need user confirmation** before externally-visible mutations (GitHub metadata, issue filing). The plan includes explicit pause points.

---

# ops-pilot tasks

### Task 1: Fix license line (item 1)

**Files:**
- Modify: `ops-pilot/README.md` (bottom of file, "License" section)

- [ ] **Step 1: Read the current license line to confirm the exact string**

```bash
grep -n "portfolio project" /Users/adnankhan/dev/ops-pilot/README.md
```

Expected output: a single match on the last line of the file.

- [ ] **Step 2: Replace the license line**

Use the Edit tool on `/Users/adnankhan/dev/ops-pilot/README.md`:

- `old_string`: `MIT © 2026 — built as a portfolio project demonstrating production-quality multi-agent AI systems.`
- `new_string`: `MIT © 2026 Adnan Khan`

- [ ] **Step 3: Verify the change**

```bash
tail -3 /Users/adnankhan/dev/ops-pilot/README.md
```

Expected: shows `## License` then blank line then `MIT © 2026 Adnan Khan` (no "portfolio project" phrase).

- [ ] **Step 4: Commit** (cwd: `$OP`)

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs: remove portfolio-project phrase from license line

The phrase read as "not maintained" to engineers evaluating the repo
for adoption. The README's depth already signals seriousness.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Add "Who this is for" line (item 3)

**Files:**
- Modify: `ops-pilot/README.md` (after the hook line, before the byline)

- [ ] **Step 1: Verify the anchor string**

```bash
grep -n "while your engineers sleep" /Users/adnankhan/dev/ops-pilot/README.md
```

Expected: single match on line 3.

- [ ] **Step 2: Insert the line**

Use the Edit tool on `/Users/adnankhan/dev/ops-pilot/README.md`:

- `old_string`:
```
**AI agents that watch your CI/CD pipelines, diagnose failures, write the fix, and open a pull request — while your engineers sleep.**

> Built by
```
- `new_string`:
```
**AI agents that watch your CI/CD pipelines, diagnose failures, write the fix, and open a pull request — while your engineers sleep.**

> **Who this is for:** platform engineering teams running 10+ services on GitHub Actions / GitLab CI / Jenkins who are tired of the 2 AM CI page.

> Built by
```

- [ ] **Step 3: Verify**

```bash
grep -A1 "Who this is for" /Users/adnankhan/dev/ops-pilot/README.md | head -5
```

Expected: shows the new blockquote line.

- [ ] **Step 4: Commit** (cwd: `$OP`)

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs: add "Who this is for" line to README hook

Specificity converts — states the target user explicitly so skimmers
can self-qualify in one sentence.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Extract Architecture and Design decisions into separate docs (item 2)

This task has multiple file changes but is one commit — it's a single logical restructure.

**Files:**
- Create: `ops-pilot/docs/ARCHITECTURE.md`
- Create: `ops-pilot/docs/DESIGN.md`
- Modify: `ops-pilot/README.md` (replace Architecture section, delete Design decisions section)

**Note on restarts:** this task uses `/tmp/` files as intermediate buffers (Steps 1 and 2). If you restart partway through, re-run Step 1 first to recreate the temp files — Step 9 deletes them.

- [ ] **Step 1: Read the current README to capture the two blocks being moved**

```bash
sed -n '166,247p' /Users/adnankhan/dev/ops-pilot/README.md > /tmp/op-architecture-block.md
sed -n '295,413p' /Users/adnankhan/dev/ops-pilot/README.md > /tmp/op-design-block.md
wc -l /tmp/op-architecture-block.md /tmp/op-design-block.md
```

Expected: ~82 lines in architecture block, ~119 lines in design block. **Confirm the last line of the design block is the closing of "Why Pydantic models between agents?"** — if not, adjust the range and retry.

- [ ] **Step 2: Verify block boundaries by inspecting first/last lines**

```bash
head -3 /tmp/op-architecture-block.md && echo "---" && tail -3 /tmp/op-architecture-block.md
echo "==="
head -3 /tmp/op-design-block.md && echo "---" && tail -3 /tmp/op-design-block.md
```

Expected first block: starts with `## Architecture`, ends with "Every agent communicates exclusively through typed Pydantic models — no raw dicts cross boundaries. Every agent is independently testable with a mock backend." (plus trailing blank lines and `---`).

Expected second block: starts with `## Design decisions`, ends with the Pydantic-models paragraph.

- [ ] **Step 3: Create `docs/ARCHITECTURE.md`**

Use the Write tool to create `/Users/adnankhan/dev/ops-pilot/docs/ARCHITECTURE.md` with content:

````markdown
# ops-pilot Architecture

Detailed structure of the ops-pilot codebase. For a high-level summary, see the [README](../README.md#architecture). For the reasoning behind these choices, see [DESIGN.md](DESIGN.md).

← [Back to README](../README.md)

---

<PASTE THE FULL CONTENT OF /tmp/op-architecture-block.md HERE — including the `## Architecture` heading and everything through the closing "independently testable" paragraph. Drop the trailing `---` separator since this file doesn't need it.>
````

Replace the `<PASTE…>` placeholder by reading `/tmp/op-architecture-block.md` and inlining its verbatim content (with the `## Architecture` heading converted to a `## File structure` heading — since the file's top H1 is already "ops-pilot Architecture", a duplicate H2 is redundant).

- [ ] **Step 4: Create `docs/DESIGN.md`**

Use the Write tool to create `/Users/adnankhan/dev/ops-pilot/docs/DESIGN.md` with content:

````markdown
# Design Decisions

The reasoning behind ops-pilot's architecture. Each section answers a "why did you choose X over Y?" question that a reviewer or customer might raise.

← [Back to README](../README.md) · [Architecture reference](ARCHITECTURE.md)

---

<PASTE THE FULL CONTENT OF /tmp/op-design-block.md HERE — drop the leading `## Design decisions` heading since the file's H1 "Design Decisions" replaces it. Keep all 14 H3 "Why X" subsections verbatim.>
````

- [ ] **Step 5: Verify both new docs render**

```bash
head -10 /Users/adnankhan/dev/ops-pilot/docs/ARCHITECTURE.md
echo "==="
head -10 /Users/adnankhan/dev/ops-pilot/docs/DESIGN.md
echo "==="
wc -l /Users/adnankhan/dev/ops-pilot/docs/ARCHITECTURE.md /Users/adnankhan/dev/ops-pilot/docs/DESIGN.md
```

Expected: both start with H1 + intro paragraph + back-link + `---`. Architecture file ~90 lines, Design file ~125 lines.

- [ ] **Step 6: Replace the README Architecture section**

Use the Edit tool on `/Users/adnankhan/dev/ops-pilot/README.md`:

- `old_string`: the full current Architecture section — from `## Architecture\n\n\`\`\`\nops-pilot/` through `Every agent communicates exclusively through typed Pydantic models — no raw dicts cross boundaries. Every agent is independently testable with a mock backend.\n\n---` (use the exact content of `/tmp/op-architecture-block.md`)
- `new_string`:
```
## Architecture

Four agents (Monitor → Triage → Fix → Notify), each extending `BaseAgent[OutputT]` and running on a generic `AgentLoop` that handles tool-use iteration. Agents communicate via Pydantic models — no raw dicts cross boundaries. Tools are permission-tiered: READ_ONLY → WRITE → REQUIRES_CONFIRMATION, enforced by `ToolRegistry`. Memory, context budgeting, trust (audit log + pre-action explanation), and multi-tenancy are isolated modules in `shared/`.

→ **[Full architecture](docs/ARCHITECTURE.md)** · **[Why these design decisions?](docs/DESIGN.md)**

---
```

If the Edit tool fails due to `old_string` being too large, fall back to: read the full README, write the full modified README via Write tool.

- [ ] **Step 7: Remove the README Design decisions section**

Use the Edit tool on `/Users/adnankhan/dev/ops-pilot/README.md`:

- `old_string`: the full Design decisions section (`## Design decisions\n\n### Why four separate agents...` through `...makes the data contract between agents explicit and type-checked.\n\n---`)
- `new_string`: (empty string — the section is deleted; the `---` separators that remain on either side will naturally collapse)

Alternative if Edit fails: use Write with the full modified README.

- [ ] **Step 8: Verify the README structure**

```bash
grep -n "^## " /Users/adnankhan/dev/ops-pilot/README.md
```

Expected section order (line numbers will vary, but headings in this order):
```
## 🎮 Live Demo
## What problem does this solve?
## Quickstart
## How it works
## Architecture
## LLM backends
## Claude Code integration
## Running tests
## License
```

Note: "Design decisions" heading must be absent. "How is this different" / "Related" / "About the author" headings are added by later tasks.

- [ ] **Step 9: Clean up temp files**

```bash
rm /tmp/op-architecture-block.md /tmp/op-design-block.md
```

- [ ] **Step 10: Commit** (cwd: `$OP`)

```bash
git add README.md docs/ARCHITECTURE.md docs/DESIGN.md
git commit -m "$(cat <<'EOF'
docs: extract Architecture and Design decisions into separate docs

The 80-line file tree and 120-line Design decisions block were
competing with the hook above the fold. Move them to docs/ and
replace with a 5-line summary plus links in the README.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Add "How is this different from…" comparison table (item 4)

**Files:**
- Modify: `ops-pilot/README.md` (insert new section between "Claude Code integration" and "Running tests")

- [ ] **Step 1: Verify the anchor — find the "Claude Code integration" section's closing boundary**

```bash
grep -n "Edit the \`\.md\` file" /Users/adnankhan/dev/ops-pilot/README.md
```

Expected: single match on a line like "Every command is defined in `.claude/commands/<name>.md` — edit the `.md` file to change how Claude approaches the task."

- [ ] **Step 2: Insert the new section**

Use the Edit tool on `/Users/adnankhan/dev/ops-pilot/README.md`:

- `old_string`:
```
Every command is defined in `.claude/commands/<name>.md` — edit the `.md` file to change how Claude approaches the task.

---

## Running tests
```
- `new_string`:
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

## Running tests
```

- [ ] **Step 3: Verify**

```bash
grep -n "^## " /Users/adnankhan/dev/ops-pilot/README.md | grep -E "(different from|Running tests)"
```

Expected: "How is this different from…" appears immediately before "Running tests" in the heading list.

- [ ] **Step 4: Commit** (cwd: `$OP`)

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs: add "How is this different from…" comparison table

Readers evaluating ops-pilot silently ask how it differs from Sweep,
Copilot Workspace, Sentry Autofix, and Aider. Answer the question.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Add "Related" section cross-linking retro-pilot (item 7)

**Files:**
- Modify: `ops-pilot/README.md` (insert between the comparison table and "Running tests")

- [ ] **Step 1: Insert the Related section**

Use the Edit tool on `/Users/adnankhan/dev/ops-pilot/README.md`:

- `old_string`:
```
| **Observability** | JSONL audit log + pre-action LLM explanation | — | GitHub-native | Sentry-native | — |

---

## Running tests
```
- `new_string`:
```
| **Observability** | JSONL audit log + pre-action LLM explanation | — | GitHub-native | Sentry-native | — |

---

## Related

**[retro-pilot](https://github.com/adnanafik/retro-pilot)** — autonomous post-mortem generator.
ops-pilot catches the failure and opens a PR. retro-pilot takes the resolved incident and produces a structured post-mortem stored in a searchable knowledge base.

---

## Running tests
```

- [ ] **Step 2: Verify**

```bash
grep -n "^## " /Users/adnankhan/dev/ops-pilot/README.md | tail -6
```

Expected order in the tail of the list: "How is this different from…", "Related", "Running tests", "License".

- [ ] **Step 3: Commit** (cwd: `$OP`)

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs: add Related section cross-linking retro-pilot

retro-pilot already links back to ops-pilot; make the link
bidirectional so readers can follow the narrative pair either way.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Rework byline and add About the author section (item 10)

**Files:**
- Modify: `ops-pilot/README.md` (byline at top; new About section near bottom, before License)

- [ ] **Step 1: Replace the top byline**

Use the Edit tool on `/Users/adnankhan/dev/ops-pilot/README.md`:

- `old_string`: `> Built by **[Adnan Khan](https://adnankhan.me)** — Sr. Director of AI Engineering · [LinkedIn](https://linkedin.com/in/passionateforinnovation) · [Portfolio](https://adnankhan.me)`
- `new_string`: `> Built by **[Adnan Khan](https://adnankhan.me)** · [LinkedIn](https://linkedin.com/in/passionateforinnovation)`

- [ ] **Step 2: Insert the About the author section before License**

Use the Edit tool on `/Users/adnankhan/dev/ops-pilot/README.md`:

- `old_string`:
```
## License

MIT © 2026 Adnan Khan
```
- `new_string`:
```
## About the author

Adnan Khan builds AI systems for platform engineering teams. [LinkedIn](https://linkedin.com/in/passionateforinnovation) · [adnankhan.me](https://adnankhan.me)

---

## License

MIT © 2026 Adnan Khan
```

- [ ] **Step 3: Verify**

```bash
head -7 /Users/adnankhan/dev/ops-pilot/README.md
echo "==="
tail -10 /Users/adnankhan/dev/ops-pilot/README.md
```

Expected top: new byline without title. Expected bottom: About the author above License.

- [ ] **Step 4: Commit** (cwd: `$OP`)

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs: move author title to About the author section

Title in top byline read like a recruiting prop. Action-oriented
phrasing in a dedicated About section at the bottom establishes
context first.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Add CONTRIBUTING.md (item 9 part A)

**Files:**
- Create: `ops-pilot/CONTRIBUTING.md`

- [ ] **Step 1: Write the file**

Use the Write tool to create `/Users/adnankhan/dev/ops-pilot/CONTRIBUTING.md` with content:

```markdown
# Contributing to ops-pilot

Thanks for considering a contribution.

## Getting started
1. Fork and clone.
2. `pip install -e ".[dev]"` (Python 3.11+).
3. `docker compose run --rm test` to run the suite.

## Finding something to work on
- Check [good first issues](https://github.com/adnanafik/ops-pilot/labels/good%20first%20issue) if you're new.
- For larger changes, open an issue first to align on scope.

## Code style
- Type hints everywhere, no `Any`.
- `ruff check .` must pass.
- pytest coverage ≥ 80% on agent logic.

## Pull requests
- One logical change per PR.
- Add or update tests.
- Short imperative commit subjects.
```

- [ ] **Step 2: Verify**

```bash
cat /Users/adnankhan/dev/ops-pilot/CONTRIBUTING.md | head -5
```

Expected: starts with `# Contributing to ops-pilot`.

- [ ] **Step 3: Commit** (cwd: `$OP`)

```bash
git add CONTRIBUTING.md
git commit -m "$(cat <<'EOF'
docs: add CONTRIBUTING.md

Short onramp for new contributors — setup, how to find a good first
issue, code style, PR expectations.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Update GitHub metadata — add missing topics (item 6)

**Files:** none — this mutates the repo on github.com, not local files.

**Pre-condition:** the executing agent MUST pause before this task and confirm with the user that the metadata change is approved (externally visible).

- [ ] **Step 1: Show the current topics and the proposed change**

```bash
gh api repos/adnanafik/ops-pilot --jq '.topics'
```

Expected current: `["ai-agents","anthropic","cicd","devops","incident-response","llm","platform-engineering","sre"]`.

Proposed final: `["ai-agents","anthropic","cicd","devops","incident-response","llm","multi-agent","platform-engineering","python","sre"]` (adds `multi-agent`, `python`).

- [ ] **Step 2: Pause for user approval**

Show the user:
- Current topics
- Proposed final topics
- The `gh` command that will run

Wait for an explicit "go ahead" before proceeding.

- [ ] **Step 3: Apply the topic update**

```bash
gh api repos/adnanafik/ops-pilot/topics -X PUT \
  -f names[]=ai-agents \
  -f names[]=anthropic \
  -f names[]=cicd \
  -f names[]=devops \
  -f names[]=incident-response \
  -f names[]=llm \
  -f names[]=multi-agent \
  -f names[]=platform-engineering \
  -f names[]=python \
  -f names[]=sre
```

Note: the topics endpoint uses `PUT` on `/topics` (replaces the full list), not `PATCH` on the root repo endpoint.

- [ ] **Step 4: Verify**

```bash
gh api repos/adnanafik/ops-pilot --jq '.topics'
```

Expected: the 10 topics in alphabetical order.

No git commit — this change is not in the repo.

---

### Task 9: File good-first-issue candidates (item 9 part B)

**Files:** none — creates issues on github.com.

**Pre-condition:** user explicitly approves which of the 5 candidates to file. Do not file all five by default.

- [ ] **Step 1: Ensure the `good first issue` label exists**

```bash
gh label list --repo adnanafik/ops-pilot | grep -i "good first issue" || \
  gh label create "good first issue" --repo adnanafik/ops-pilot --color 7057ff --description "Good entry point for new contributors"
```

Expected: either the label already exists, or it is created.

- [ ] **Step 2: Present the 5 candidates to the user and collect approval**

Show the user this list:

1. **Add a CircleCI provider** — pattern from `providers/github.py` / `gitlab.py` / `jenkins.py`; `/new-provider` slash command exists to scaffold.
2. **Add a new demo scenario** — schema in `demo/scenarios/*.json`; `/scenario` slash command exists.
3. **Improve the "ANTHROPIC_API_KEY not set" error message** — currently cryptic; should point to setup docs.
4. **Add a `--verbose` flag to `scripts/watch_and_fix.py`** — enables debug logging.
5. **Add a deployment guide for Fly.io or Railway** — docs-only addition under `docs/`.

Wait for user approval. They may approve all, some, or none, and may tweak wording.

- [ ] **Step 3: For each approved candidate, create the issue**

For each approved candidate, run (substituting the approved title and body):

```bash
gh issue create \
  --repo adnanafik/ops-pilot \
  --label "good first issue" \
  --title "<approved title>" \
  --body "$(cat <<'EOF'
<approved body — 1-3 sentences describing the task, pointers to relevant files/patterns, acceptance criteria>
EOF
)"
```

Draft bodies the user can edit:

**Candidate 1 body:**
```
Add support for CircleCI as a CI provider, following the existing pattern in `providers/github.py`, `providers/gitlab.py`, `providers/jenkins.py`.

The `/new-provider` slash command in `.claude/commands/new-provider.md` scaffolds the full skeleton — run it with "CircleCI" as the argument.

**Acceptance:**
- `providers/circleci.py` implements the `CIProvider` ABC (see `providers/base.py`).
- `providers/factory.py` routes `provider: circleci` to the new class.
- Tests in `tests/test_circleci_provider.py` mock the CircleCI API and cover `get_failures`, `open_draft_pr`, `get_log`.
- README `LLM backends` section (or a new "CI providers" section) notes CircleCI is supported.
```

**Candidate 2 body:**
```
Add a new realistic CI failure scenario to `demo/scenarios/`. The existing three (null pointer auth, missing dependency docker, flaky integration test) are good templates.

The `/scenario` slash command in `.claude/commands/scenario.md` generates a scenario JSON from a failure description.

**Acceptance:**
- New file under `demo/scenarios/<name>.json` conforming to the existing schema.
- The demo UI lists it as a selectable scenario.
- Scenario runs cleanly end-to-end when played through the demo.
```

**Candidate 3 body:**
```
When `ANTHROPIC_API_KEY` is unset, ops-pilot currently fails with a cryptic error. Improve the message to explicitly state:
1. Which env var is missing.
2. A pointer to the setup docs (`.env.example`, README Quickstart).

**Acceptance:**
- Running `python3 scripts/watch_and_fix.py --once` with no API key prints a message containing "ANTHROPIC_API_KEY" and a link to the Quickstart section.
- Exit code is non-zero.
- Test added that mocks a missing env var and asserts the message format.
```

**Candidate 4 body:**
```
Add a `--verbose` / `-v` flag to `scripts/watch_and_fix.py` that enables DEBUG-level logging across all agents.

**Acceptance:**
- `python3 scripts/watch_and_fix.py --once --verbose` logs tool calls and agent-loop turns at DEBUG level.
- Without the flag, logging stays at the current INFO level.
- Test asserts that setting the flag bumps the root logger's level.
```

**Candidate 5 body:**
```
Write a short deployment guide for running ops-pilot on Fly.io or Railway (pick one; the other is a follow-up).

**Acceptance:**
- `docs/deploy-<fly|railway>.md` walks through: account setup, secret config, deploying the `ops-pilot-watcher` Compose service, observing the first run.
- README Quickstart section links to the new guide.
- Guide is tested end-to-end by the author (or explicitly marks "untested" with a call for feedback).
```

- [ ] **Step 4: Verify the issues**

```bash
gh issue list --repo adnanafik/ops-pilot --label "good first issue"
```

Expected: the approved issues appear with the label.

No git commit — issues live on GitHub.

---

# retro-pilot tasks

### Task 10: Add badges (item 5)

**Files:**
- Modify: `retro-pilot/README.md` (insert after the byline, before the `---` separator)

- [ ] **Step 1: Verify the current byline and surrounding context**

```bash
sed -n '3,9p' /Users/adnankhan/dev/retro-pilot/README.md
```

Expected: line 5 is the current byline (`**Built by [Adnan Khan](https://adnankhan.me)** ...`), line 7 is `---`.

- [ ] **Step 2: Insert the badges**

Use the Edit tool on `/Users/adnankhan/dev/retro-pilot/README.md`:

- `old_string`:
```
**Built by [Adnan Khan](https://adnankhan.me)** — Sr. Director of AI Engineering · [LinkedIn](https://linkedin.com/in/passionateforinnovation) · [Portfolio](https://adnankhan.me)

---
```
- `new_string`:
```
**Built by [Adnan Khan](https://adnankhan.me)** — Sr. Director of AI Engineering · [LinkedIn](https://linkedin.com/in/passionateforinnovation) · [Portfolio](https://adnankhan.me)

[![Tests](https://img.shields.io/github/actions/workflow/status/adnanafik/retro-pilot/retro-pilot-ci.yml?label=tests&style=flat-square)](https://github.com/adnanafik/retro-pilot/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

---
```

(The byline remains unchanged in this task — Task 13 rewrites it.)

- [ ] **Step 3: Verify**

```bash
grep -n "shields.io" /Users/adnankhan/dev/retro-pilot/README.md
```

Expected: three consecutive lines of badge markdown.

- [ ] **Step 4: Verify the Tests badge URL resolves**

```bash
curl -sI "https://img.shields.io/github/actions/workflow/status/adnanafik/retro-pilot/retro-pilot-ci.yml?label=tests&style=flat-square" | head -1
```

Expected: `HTTP/2 200`.

- [ ] **Step 5: Commit** (cwd: `$RP`)

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs: add Tests / Python / License badges

Match ops-pilot's badge set. Badge-less README reads as a lesser
sibling and signals "abandoned" to first-time visitors.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Add "Who this is for" line (item 3)

**Files:**
- Modify: `retro-pilot/README.md` (after the hook line)

- [ ] **Step 1: Verify the anchor**

```bash
grep -n "ops-pilot catches the failure" /Users/adnankhan/dev/retro-pilot/README.md
```

Expected: single match on line 3.

- [ ] **Step 2: Insert the line**

Use the Edit tool on `/Users/adnankhan/dev/retro-pilot/README.md`:

- `old_string`:
```
> ops-pilot catches the failure. retro-pilot learns from it.

**Built by
```
- `new_string`:
```
> ops-pilot catches the failure. retro-pilot learns from it.

> **Who this is for:** platform and SRE teams that want every resolved incident to produce a structured post-mortem — without the on-call engineer having to write one from scratch.

**Built by
```

- [ ] **Step 3: Verify**

```bash
grep -A1 "Who this is for" /Users/adnankhan/dev/retro-pilot/README.md | head -3
```

Expected: the new line appears.

- [ ] **Step 4: Commit** (cwd: `$RP`)

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs: add "Who this is for" line to README hook

State the target reader explicitly so skimmers can self-qualify.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: Add "How it compares to alternatives" section (item 4)

**Files:**
- Modify: `retro-pilot/README.md` (insert below the existing "How it's different from ops-pilot" section)

- [ ] **Step 1: Verify the anchor — the `---` separator between the existing ops-pilot comparison and the next section**

```bash
grep -n "post-mortems are prose-heavy and need semantic similarity" /Users/adnankhan/dev/retro-pilot/README.md
awk '/^## /{print NR": "$0}' /Users/adnankhan/dev/retro-pilot/README.md
```

Expected: the "prose-heavy" phrase appears as the closing sentence of the "Semantic vector store" subsection inside "How it's different from ops-pilot". The headings list shows `## Knowledge base` as the next H2. Insertion point: the `---` separator between those two.

- [ ] **Step 2: Insert the new section at that separator**

Use the Edit tool on `/Users/adnankhan/dev/retro-pilot/README.md`:

- `old_string`:
```
ops-pilot's token Jaccard works well for structured CI failure data; post-mortems are prose-heavy and need semantic similarity.

---

## Knowledge base
```
- `new_string`:
```
ops-pilot's token Jaccard works well for structured CI failure data; post-mortems are prose-heavy and need semantic similarity.

---

## How it compares to alternatives

| | retro-pilot | Blameless | incident.io | FireHydrant | Rootly |
|---|---|---|---|---|---|
| **Category** | Autonomous agent (single-purpose) | IM platform | IM platform | IM platform | IM platform |
| **Post-mortem** | Fully generated from evidence | Human-authored with AI help | Human-authored with AI help | Template-driven | Template-driven |
| **Evidence collection** | Automatic (Log / Metrics / Git / Slack workers) | Manual + integrations | Manual + integrations | Manual + integrations | Manual + integrations |
| **Evaluation** | LLM-as-judge, 3-cycle revision loop | Human review | Human review | Human review | Human review |

---

## Knowledge base
```

- [ ] **Step 3: Verify**

```bash
grep -n "^## " /Users/adnankhan/dev/retro-pilot/README.md
```

Expected: "How it compares to alternatives" sits between "How it's different from ops-pilot" (implicit — the older section doesn't have an H2, the ops-pilot comparison heading is "How it's different from ops-pilot") and "Knowledge base".

If the older section's heading level differs from expected, adjust — the goal is that both comparison sections appear in the README with the new one immediately before "Knowledge base".

- [ ] **Step 4: Commit** (cwd: `$RP`)

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs: add "How it compares to alternatives" section

The existing "How it's different from ops-pilot" section serves
readers figuring out the project pair. The new section answers the
question from readers evaluating retro-pilot standalone against IM
platforms (Blameless, incident.io, FireHydrant, Rootly).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: Rework byline, add About the author section, add CONTRIBUTING.md (items 10 + 9A, batched)

**Files:**
- Modify: `retro-pilot/README.md` (byline + new About section)
- Create: `retro-pilot/CONTRIBUTING.md`

- [ ] **Step 1: Replace the top byline and normalize to blockquote**

Use the Edit tool on `/Users/adnankhan/dev/retro-pilot/README.md`:

- `old_string`: `**Built by [Adnan Khan](https://adnankhan.me)** — Sr. Director of AI Engineering · [LinkedIn](https://linkedin.com/in/passionateforinnovation) · [Portfolio](https://adnankhan.me)`
- `new_string`: `> Built by **[Adnan Khan](https://adnankhan.me)** · [LinkedIn](https://linkedin.com/in/passionateforinnovation)`

- [ ] **Step 2: Insert About the author section before License**

Use the Edit tool on `/Users/adnankhan/dev/retro-pilot/README.md`:

- `old_string`:
```
## License

MIT
```
- `new_string`:
```
## About the author

Adnan Khan builds AI systems for platform engineering teams. [LinkedIn](https://linkedin.com/in/passionateforinnovation) · [adnankhan.me](https://adnankhan.me)

---

## License

MIT
```

- [ ] **Step 3: Create CONTRIBUTING.md**

Use the Write tool to create `/Users/adnankhan/dev/retro-pilot/CONTRIBUTING.md` with content:

```markdown
# Contributing to retro-pilot

Thanks for considering a contribution.

## Getting started
1. Fork and clone.
2. `pip install -e ".[dev]"` (Python 3.11+).
3. `docker compose run --rm test` to run the suite.

## Finding something to work on
- Check [good first issues](https://github.com/adnanafik/retro-pilot/labels/good%20first%20issue) if you're new.
- For larger changes, open an issue first to align on scope.

## Code style
- Type hints everywhere, no `Any`.
- `ruff check .` must pass.
- pytest coverage ≥ 85% on agent logic.

## Pull requests
- One logical change per PR.
- Add or update tests.
- Short imperative commit subjects.
```

- [ ] **Step 4: Verify all three changes**

```bash
head -7 /Users/adnankhan/dev/retro-pilot/README.md
echo "==="
tail -12 /Users/adnankhan/dev/retro-pilot/README.md
echo "==="
head -3 /Users/adnankhan/dev/retro-pilot/CONTRIBUTING.md
```

Expected:
- Top: blockquote byline without title.
- Bottom: About the author section above License.
- CONTRIBUTING.md starts with `# Contributing to retro-pilot`.

- [ ] **Step 5: Commit** (cwd: `$RP`)

```bash
git add README.md CONTRIBUTING.md
git commit -m "$(cat <<'EOF'
docs: rework byline, add About the author section, add CONTRIBUTING.md

- Top byline: drop title, drop redundant Portfolio chip, normalize
  to blockquote format to match ops-pilot.
- Add About the author section at the bottom with action-oriented
  phrasing ("builds AI systems for platform engineering teams").
- Add CONTRIBUTING.md so new contributors have an onramp.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: Update GitHub metadata + file good-first-issue candidates (items 6 + 9B, retro-pilot)

**Files:** none — mutates repo on github.com.

**Pre-condition:** user approves both the metadata change and the candidate issues. Explicit pause before mutations.

- [ ] **Step 1: Show the current metadata and the proposed change**

```bash
gh api repos/adnanafik/retro-pilot --jq '{homepage, topics}'
```

Expected current: `{"homepage": null, "topics": []}`.

Proposed:
- Homepage: `https://adnanafik.github.io/retro-pilot/`
- Topics: `ai-agents`, `anthropic`, `chromadb`, `incident-management`, `llm`, `multi-agent`, `post-mortem`, `python`, `sre`

- [ ] **Step 2: Pause for user approval of the metadata change**

Wait for explicit go-ahead.

- [ ] **Step 3: Apply homepage update**

```bash
gh api repos/adnanafik/retro-pilot -X PATCH -f homepage="https://adnanafik.github.io/retro-pilot/"
```

- [ ] **Step 4: Apply topics update**

```bash
gh api repos/adnanafik/retro-pilot/topics -X PUT \
  -f names[]=ai-agents \
  -f names[]=anthropic \
  -f names[]=chromadb \
  -f names[]=incident-management \
  -f names[]=llm \
  -f names[]=multi-agent \
  -f names[]=post-mortem \
  -f names[]=python \
  -f names[]=sre
```

- [ ] **Step 5: Verify metadata**

```bash
gh api repos/adnanafik/retro-pilot --jq '{homepage, topics}'
```

Expected: homepage set, topics list matches the 9 proposed.

- [ ] **Step 6: Ensure the `good first issue` label exists**

```bash
gh label list --repo adnanafik/retro-pilot | grep -i "good first issue" || \
  gh label create "good first issue" --repo adnanafik/retro-pilot --color 7057ff --description "Good entry point for new contributors"
```

- [ ] **Step 7: Present the 5 candidates and collect user approval**

Show the user:

1. **Add a JiraWorker evidence collector** — follows existing Log / Metrics / Git / Slack worker pattern under `agents/` (or wherever evidence workers live).
2. **Add a new demo scenario** — add to `demo/scenarios/`; existing three (Redis cascade SEV1, deploy regression SEV2, certificate expiry SEV2) are templates.
3. **Add a `scripts/list_postmortems.py` CLI** — lists stored post-mortems from ChromaDB with filters (date range, severity).
4. **Export a post-mortem to a plain Markdown file** — given a post-mortem ID, write a Markdown rendering.
5. **Add a PagerDutyWorker evidence collector** — same pattern as Jira.

Wait for explicit approval.

- [ ] **Step 8: For each approved candidate, file the issue**

Draft bodies (edit per approval):

**Candidate 1 body:**
```
Add a JiraWorker evidence collector that can fetch Jira tickets linked to an incident (from comments, Slack mentions, or explicit incident metadata).

Pattern: see the existing evidence workers in `agents/` (LogWorker, MetricsWorker, GitWorker, SlackWorker). Each is a scoped AgentLoop with a READ_ONLY tool list.

**Acceptance:**
- `agents/jira_worker.py` implements the worker.
- `tools/jira_tool.py` (or similar) wraps the Jira REST API.
- Tests mock the Jira API and verify the worker's summary output.
- `retro-pilot.example.yml` shows the Jira endpoint config.
```

**Candidate 2 body:**
```
Add a new realistic incident scenario to `demo/scenarios/`. The existing three (Redis cascade SEV1, deploy regression SEV2, certificate expiry SEV2) are templates.

**Acceptance:**
- New JSON file under `demo/scenarios/` conforming to the existing schema.
- Demo UI lists it as a selectable scenario.
- End-to-end playthrough produces a valid draft post-mortem.
```

**Candidate 3 body:**
```
Add `scripts/list_postmortems.py` that queries ChromaDB and prints a table of stored post-mortems with filters.

**Acceptance:**
- CLI supports `--since DATE`, `--severity {SEV1|SEV2|SEV3}`, `--service NAME`.
- Output is a plain table with incident_id, title, severity, date, evaluator score.
- Test uses a temp ChromaDB directory and verifies filter behavior.
```

**Candidate 4 body:**
```
Add export-to-Markdown for stored post-mortems: `python scripts/export_postmortem.py --id INC-...` writes a plain Markdown file of the post-mortem.

**Acceptance:**
- Generates a human-readable Markdown file (no embedded JSON).
- Includes: title, executive summary, timeline, root cause, contributing factors, action items, similar incidents.
- Test round-trips a fixture post-mortem through export and verifies structure.
```

**Candidate 5 body:**
```
Add a PagerDutyWorker evidence collector that can fetch PagerDuty incident records and timeline events.

Pattern: same as the existing evidence workers.

**Acceptance:**
- `agents/pagerduty_worker.py` implements the worker.
- Tool wraps the PagerDuty REST API with the `incidents:read` scope.
- Tests mock the API and verify the worker's summary output.
- `retro-pilot.example.yml` shows the PagerDuty endpoint config.
```

For each approved candidate:

```bash
gh issue create \
  --repo adnanafik/retro-pilot \
  --label "good first issue" \
  --title "<approved title>" \
  --body "$(cat <<'EOF'
<approved body>
EOF
)"
```

- [ ] **Step 9: Verify**

```bash
gh issue list --repo adnanafik/retro-pilot --label "good first issue"
```

Expected: the approved issues appear with the label.

No git commit — all changes in this task are on GitHub.

---

# Wrap-up

After Task 14:

- [ ] **Step 1: Local verification**

Visit both READMEs on github.com (`main` branch) and confirm:
- Hook visible above the fold without scrolling past a wall of text.
- Three badges render on retro-pilot.
- "How is this different from…" / "How it compares to alternatives" tables render correctly.
- Cross-links (ops-pilot → retro-pilot and vice versa) work.
- `docs/ARCHITECTURE.md` and `docs/DESIGN.md` render on github.com.

- [ ] **Step 2: Metadata verification**

```bash
gh api repos/adnanafik/ops-pilot --jq '{description, homepage, topics}'
gh api repos/adnanafik/retro-pilot --jq '{description, homepage, topics}'
```

Expected: both have description + homepage + topics populated.

- [ ] **Step 3: Good-first-issues verification**

```bash
gh issue list --repo adnanafik/ops-pilot --label "good first issue"
gh issue list --repo adnanafik/retro-pilot --label "good first issue"
```

Expected: approved issues appear in each.

- [ ] **Step 4: Push commits**

```bash
cd /Users/adnankhan/dev/ops-pilot && git push
cd /Users/adnankhan/dev/retro-pilot && git push
```

Pause before each `git push` and confirm with the user — pushes are externally visible.

---

## Appendix: running count

| Repo | Git commits | External (gh) actions |
|---|---|---|
| ops-pilot | 7 (tasks 1-7) | Topics + up to 5 issues (tasks 8-9) |
| retro-pilot | 4 (tasks 10-13) | Homepage + topics + up to 5 issues (task 14) |

Item-to-task mapping:

| Feedback item | Task(s) |
|---|---|
| 1. Remove "portfolio project" phrase | 1 |
| 2. Restructure README (ops-pilot) | 3 |
| 3. "Who this is for" | 2, 11 |
| 4. Comparison table | 4, 12 |
| 5. retro-pilot badges | 10 |
| 6. GitHub metadata | 8, 14 |
| 7. Related cross-link | 5 |
| 8. PyPI | **out of scope** |
| 9. CONTRIBUTING.md + good-first-issues | 7, 9, 13, 14 |
| 10. Byline + About the author | 6, 13 |
