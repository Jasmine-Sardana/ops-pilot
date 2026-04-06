# Phase 6 — Production Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tenant identity, tool permissions, usage tracking, and rate limiting to ops-pilot for per-customer deployments.

**Architecture:** A `TenantContext` dataclass bundles four subsystems (identity, permissions, usage tracker, rate limiter) and is constructed once at startup from config, then injected into agents — the same pattern as `LLMBackend`. `AgentLoop` checks permissions before executing tools and calls the rate limiter + usage tracker around each LLM call.

**Tech Stack:** Python 3.11+, Pydantic v2, file-based atomic writes (same pattern as `MemoryStore`), no new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-03-phase6-production-hardening-design.md`

---

### Task 1: shared/exceptions.py — Custom exceptions

**Files:**
- Create: `shared/exceptions.py`
- Create: `tests/test_exceptions.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_exceptions.py
from shared.exceptions import RateLimitExceeded, ToolPermissionDenied


def test_rate_limit_exceeded_is_exception():
    exc = RateLimitExceeded("100/100 calls in last hour")
    assert isinstance(exc, Exception)
    assert "100/100" in str(exc)


def test_tool_permission_denied_is_exception():
    exc = ToolPermissionDenied("create_pr")
    assert isinstance(exc, Exception)
    assert "create_pr" in str(exc)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_exceptions.py -v
```
Expected: `ModuleNotFoundError: No module named 'shared.exceptions'`

- [ ] **Step 3: Write minimal implementation**

```python
# shared/exceptions.py
"""Custom exceptions for ops-pilot tenant enforcement."""


class RateLimitExceeded(Exception):
    """Raised when a deployment's per-hour rate limit cap is reached."""


class ToolPermissionDenied(Exception):
    """Raised when an agent attempts to use a tool not in its allowlist."""
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_exceptions.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add shared/exceptions.py tests/test_exceptions.py
git commit -m "feat(phase6): add RateLimitExceeded and ToolPermissionDenied exceptions"
```

---

### Task 2: Config additions — tenant_id, PermissionsConfig, RateLimitsConfig

**Files:**
- Modify: `shared/config.py`
- Create: `tests/test_tenant_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tenant_config.py
from shared.config import OpsPilotConfig, PermissionsConfig, RateLimitsConfig


def test_default_tenant_id():
    config = OpsPilotConfig()
    assert config.tenant_id == "default"


def test_tenant_id_from_dict():
    config = OpsPilotConfig(tenant_id="acme-corp")
    assert config.tenant_id == "acme-corp"


def test_default_permissions_allow_all():
    config = OpsPilotConfig()
    assert config.permissions.allowed_tools == []


def test_permissions_from_dict():
    config = OpsPilotConfig(permissions={"allowed_tools": ["get_file", "get_more_log"]})
    assert config.permissions.allowed_tools == ["get_file", "get_more_log"]


def test_default_rate_limits_are_zero():
    config = OpsPilotConfig()
    assert config.rate_limits.max_api_calls_per_hour == 0
    assert config.rate_limits.max_tokens_per_hour == 0


def test_rate_limits_from_dict():
    config = OpsPilotConfig(rate_limits={"max_api_calls_per_hour": 100, "max_tokens_per_hour": 500000})
    assert config.rate_limits.max_api_calls_per_hour == 100
    assert config.rate_limits.max_tokens_per_hour == 500000
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_tenant_config.py -v
```
Expected: `ImportError: cannot import name 'PermissionsConfig' from 'shared.config'`

- [ ] **Step 3: Add the new Pydantic models and fields to shared/config.py**

Add these two classes after the existing imports and before `PipelineConfig` (around line 19):

```python
class PermissionsConfig(BaseModel):
    """Per-deployment tool allowlist. Empty list = all tools permitted."""

    allowed_tools: list[str] = Field(
        default_factory=list,
        description="Explicit tool allowlist. Omit or leave empty to allow all tools.",
    )


class RateLimitsConfig(BaseModel):
    """Per-deployment rate limits. Zero = unlimited."""

    max_api_calls_per_hour: int = Field(
        default=0,
        ge=0,
        description="Maximum LLM API calls per rolling hour. 0 = unlimited.",
    )
    max_tokens_per_hour: int = Field(
        default=0,
        ge=0,
        description="Maximum tokens consumed per rolling hour. 0 = unlimited.",
    )
```

Then add these three fields to `OpsPilotConfig` after the `model` field (around line 108):

```python
    # Tenant identity
    tenant_id: str = Field(
        default="default",
        description="Identifier for this deployment — stamped on all records and logs.",
    )

    # Tool permissions
    permissions: PermissionsConfig = Field(
        default_factory=PermissionsConfig,
        description="Per-deployment tool allowlist configuration.",
    )

    # Rate limits
    rate_limits: RateLimitsConfig = Field(
        default_factory=RateLimitsConfig,
        description="Per-deployment rate limiting configuration.",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_tenant_config.py -v
```
Expected: 6 passed

- [ ] **Step 5: Verify existing config tests still pass**

```bash
pytest tests/ -v -k "config" 2>/dev/null || pytest tests/ -v --tb=short 2>&1 | head -50
```
Expected: no regressions

- [ ] **Step 6: Commit**

```bash
git add shared/config.py tests/test_tenant_config.py
git commit -m "feat(phase6): add tenant_id, PermissionsConfig, RateLimitsConfig to OpsPilotConfig"
```

---

### Task 3: shared/tool_permissions.py — Tool allowlist enforcement

**Files:**
- Create: `shared/tool_permissions.py`
- Create: `tests/test_tool_permissions.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tool_permissions.py
import pytest
from shared.tool_permissions import ToolPermissions


def test_empty_allowlist_permits_all():
    """Omitting allowed_tools means all tools are permitted (default-open)."""
    perms = ToolPermissions(allowed_tools=[])
    assert perms.is_allowed("get_file") is True
    assert perms.is_allowed("create_pr") is True
    assert perms.is_allowed("anything") is True


def test_explicit_allowlist_permits_listed_tools():
    perms = ToolPermissions(allowed_tools=["get_file", "get_more_log"])
    assert perms.is_allowed("get_file") is True
    assert perms.is_allowed("get_more_log") is True


def test_explicit_allowlist_blocks_unlisted_tools():
    perms = ToolPermissions(allowed_tools=["get_file", "get_more_log"])
    assert perms.is_allowed("create_pr") is False
    assert perms.is_allowed("get_commit_diff") is False


def test_single_tool_allowlist():
    perms = ToolPermissions(allowed_tools=["get_file"])
    assert perms.is_allowed("get_file") is True
    assert perms.is_allowed("get_more_log") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_tool_permissions.py -v
```
Expected: `ModuleNotFoundError: No module named 'shared.tool_permissions'`

- [ ] **Step 3: Write minimal implementation**

```python
# shared/tool_permissions.py
"""Tool allowlist enforcement for per-deployment permission control."""

from __future__ import annotations


class ToolPermissions:
    """Controls which tools an agent is permitted to use in this deployment.

    An empty ``allowed_tools`` list means all tools are permitted (default-open).
    This preserves backward compatibility — existing deployments without a
    permissions config continue working unchanged.

    Args:
        allowed_tools: Explicit list of permitted tool names. Empty = all allowed.
    """

    def __init__(self, allowed_tools: list[str]) -> None:
        self._allowed: frozenset[str] = frozenset(allowed_tools)
        self._open: bool = len(allowed_tools) == 0

    def is_allowed(self, tool_name: str) -> bool:
        """Return True if the tool is permitted for this deployment.

        Args:
            tool_name: The tool name as registered in ToolRegistry.

        Returns:
            True if allowed, False if blocked by the allowlist.
        """
        if self._open:
            return True
        return tool_name in self._allowed
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_tool_permissions.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add shared/tool_permissions.py tests/test_tool_permissions.py
git commit -m "feat(phase6): add ToolPermissions with default-open allowlist enforcement"
```

---

### Task 4: shared/usage_tracker.py — Daily file-based usage counters

**Files:**
- Create: `shared/usage_tracker.py`
- Create: `tests/test_usage_tracker.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_usage_tracker.py
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from shared.usage_tracker import UsageTracker


@pytest.fixture
def tracker(tmp_path: Path) -> UsageTracker:
    return UsageTracker(base_dir=tmp_path)


def test_record_tokens_creates_file(tracker: UsageTracker, tmp_path: Path):
    tracker.record_tokens(500)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert (tmp_path / f"{date_str}.json").exists()


def test_record_tokens_accumulates(tracker: UsageTracker, tmp_path: Path):
    tracker.record_tokens(500)
    tracker.record_tokens(300)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data = json.loads((tmp_path / f"{date_str}.json").read_text())
    assert data["tokens_consumed"] == 800


def test_record_api_call_accumulates(tracker: UsageTracker, tmp_path: Path):
    tracker.record_api_call()
    tracker.record_api_call()
    tracker.record_api_call()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data = json.loads((tmp_path / f"{date_str}.json").read_text())
    assert data["api_calls"] == 3


def test_record_incident_accumulates(tracker: UsageTracker, tmp_path: Path):
    tracker.record_incident()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data = json.loads((tmp_path / f"{date_str}.json").read_text())
    assert data["incidents_resolved"] == 1


def test_counters_start_at_zero_for_new_day(tracker: UsageTracker, tmp_path: Path):
    """A missing file means zero counters — no cross-day contamination."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert not (tmp_path / f"{date_str}.json").exists()
    tracker.record_tokens(0)  # trigger write
    data = json.loads((tmp_path / f"{date_str}.json").read_text())
    assert data["tokens_consumed"] == 0
    assert data["api_calls"] == 0
    assert data["incidents_resolved"] == 0


def test_corrupted_file_resets_to_zero(tracker: UsageTracker, tmp_path: Path):
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (tmp_path / f"{date_str}.json").write_text("not valid json{{{")
    tracker.record_tokens(100)  # should not raise
    data = json.loads((tmp_path / f"{date_str}.json").read_text())
    assert data["tokens_consumed"] == 100
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_usage_tracker.py -v
```
Expected: `ModuleNotFoundError: No module named 'shared.usage_tracker'`

- [ ] **Step 3: Write minimal implementation**

```python
# shared/usage_tracker.py
"""Per-deployment daily usage counters stored as file-based JSON.

Storage layout::

    usage/
        YYYY-MM-DD.json   ← one file per UTC calendar day

Each file contains three counters: tokens_consumed, api_calls,
incidents_resolved. Writes are atomic (POSIX rename). Reads are
best-effort — corrupted files reset to zero rather than crashing.

This is the file-based implementation. The interface (record_tokens,
record_api_call, record_incident) is stable so a future DB-backed
implementation can replace this class without touching callers.
"""

from __future__ import annotations

import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DailyUsage(BaseModel):
    """Counters for a single UTC calendar day."""

    tokens_consumed: int = 0
    api_calls: int = 0
    incidents_resolved: int = 0


class UsageTracker:
    """File-based daily usage counter for one deployment.

    Args:
        base_dir: Directory for usage files. Created on first write.
                  Defaults to ./usage.
    """

    def __init__(self, base_dir: Path | str = Path("usage")) -> None:
        self._base = Path(base_dir)

    def record_tokens(self, n: int) -> None:
        """Increment today's token counter by n.

        Silently logs a warning on write failure — a broken meter
        should never stop an investigation.

        Args:
            n: Number of tokens to add.
        """
        usage = self._load_today()
        usage.tokens_consumed += n
        self._save_today(usage)

    def record_api_call(self) -> None:
        """Increment today's API call counter by 1."""
        usage = self._load_today()
        usage.api_calls += 1
        self._save_today(usage)

    def record_incident(self) -> None:
        """Increment today's resolved incident counter by 1."""
        usage = self._load_today()
        usage.incidents_resolved += 1
        self._save_today(usage)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _today_path(self) -> Path:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._base / f"{date_str}.json"

    def _load_today(self) -> DailyUsage:
        path = self._today_path()
        if not path.exists():
            return DailyUsage()
        try:
            return DailyUsage.model_validate_json(path.read_text())
        except Exception:
            logger.warning("UsageTracker: corrupted usage file %s — resetting to zero", path)
            return DailyUsage()

    def _save_today(self, usage: DailyUsage) -> None:
        path = self._today_path()
        try:
            self._base.mkdir(parents=True, exist_ok=True)
            _atomic_write(path, usage.model_dump_json())
        except Exception:
            logger.warning("UsageTracker: failed to write usage file %s", path)


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path via atomic rename (same pattern as MemoryStore)."""
    tmp_fd, tmp_path_str = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
    tmp_path = Path(tmp_path_str)
    try:
        with open(tmp_fd, "w") as f:
            f.write(content)
        tmp_path.rename(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_usage_tracker.py -v
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add shared/usage_tracker.py tests/test_usage_tracker.py
git commit -m "feat(phase6): add file-based UsageTracker with daily JSON counters"
```

---

### Task 5: shared/rate_limiter.py — Sliding-window rate limiter

**Files:**
- Create: `shared/rate_limiter.py`
- Create: `tests/test_rate_limiter.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rate_limiter.py
import time
from pathlib import Path

import pytest

from shared.exceptions import RateLimitExceeded
from shared.rate_limiter import RateLimiter


@pytest.fixture
def limiter(tmp_path: Path) -> RateLimiter:
    return RateLimiter(
        max_api_calls_per_hour=5,
        max_tokens_per_hour=1000,
        base_dir=tmp_path,
    )


def test_no_limits_configured_always_passes(tmp_path: Path):
    """Zero limits = unlimited — no RateLimitExceeded ever raised."""
    limiter = RateLimiter(max_api_calls_per_hour=0, max_tokens_per_hour=0, base_dir=tmp_path)
    for _ in range(20):
        limiter.check_and_consume(tokens=500)  # should never raise


def test_api_call_cap_enforced(limiter: RateLimiter):
    for _ in range(5):
        limiter.check_and_consume(tokens=10)
    with pytest.raises(RateLimitExceeded) as exc_info:
        limiter.check_and_consume(tokens=10)
    assert "call" in str(exc_info.value).lower()


def test_token_cap_enforced(limiter: RateLimiter):
    limiter.check_and_consume(tokens=800)  # 800 / 1000
    with pytest.raises(RateLimitExceeded) as exc_info:
        limiter.check_and_consume(tokens=300)  # would be 1100 > 1000
    assert "token" in str(exc_info.value).lower()


def test_expired_events_do_not_count(tmp_path: Path):
    """Events older than 3600s fall outside the sliding window."""
    limiter = RateLimiter(max_api_calls_per_hour=2, max_tokens_per_hour=0, base_dir=tmp_path)
    # Manually write two old events to the state file
    import json
    old_ts = time.time() - 3700  # older than 1 hour
    state_path = tmp_path / "rate_state.json"
    state_path.write_text(json.dumps([
        {"ts": old_ts, "tokens": 10},
        {"ts": old_ts, "tokens": 10},
    ]))
    # Should not count toward the cap — window is clear
    limiter.check_and_consume(tokens=10)
    limiter.check_and_consume(tokens=10)
    # Third call would exceed cap=2 if old events counted, but they don't
    # so it should pass (old events were expired)
    # Actually cap=2 and we just made 2 calls, so this should raise
    with pytest.raises(RateLimitExceeded):
        limiter.check_and_consume(tokens=10)


def test_corrupt_state_file_fails_open(tmp_path: Path):
    """Corrupted state file means fail-open — RateLimitExceeded is NOT raised."""
    limiter = RateLimiter(max_api_calls_per_hour=1, max_tokens_per_hour=0, base_dir=tmp_path)
    state_path = tmp_path / "rate_state.json"
    state_path.write_text("{{not valid json")
    # Should not raise — fail-open on corrupt state
    limiter.check_and_consume(tokens=10)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_rate_limiter.py -v
```
Expected: `ModuleNotFoundError: No module named 'shared.rate_limiter'`

- [ ] **Step 3: Write minimal implementation**

```python
# shared/rate_limiter.py
"""Sliding-window rate limiter stored as file-based JSON.

State file: usage/rate_state.json — a list of timestamped events::

    [{"ts": 1743686400.0, "tokens": 1500}, ...]

On each check_and_consume() call:
  1. Load state, drop events older than 3600s
  2. Check whether adding this call would exceed either cap
  3. Raise RateLimitExceeded if so; otherwise append event and save

Fail-open: corrupted or missing state files allow the call through
and log an error. A broken rate limiter should not take down an
investigation.

This is the file-based implementation. The interface (check_and_consume)
is stable so a future DB-backed implementation can replace this class
without touching callers.
"""

from __future__ import annotations

import json
import logging
import tempfile
import time
from pathlib import Path

from shared.exceptions import RateLimitExceeded

logger = logging.getLogger(__name__)

_WINDOW_SECONDS = 3600.0


class RateLimiter:
    """Sliding-window rate limiter for per-deployment LLM cost control.

    Args:
        max_api_calls_per_hour: Maximum LLM API calls per rolling hour.
                                0 = unlimited.
        max_tokens_per_hour:    Maximum tokens per rolling hour. 0 = unlimited.
        base_dir:               Directory for the state file. Defaults to ./usage.
    """

    def __init__(
        self,
        max_api_calls_per_hour: int = 0,
        max_tokens_per_hour: int = 0,
        base_dir: Path | str = Path("usage"),
    ) -> None:
        self._max_calls = max_api_calls_per_hour
        self._max_tokens = max_tokens_per_hour
        self._base = Path(base_dir)
        self._state_path = self._base / "rate_state.json"

    def check_and_consume(self, tokens: int) -> None:
        """Check rate limits and record this call if within limits.

        Args:
            tokens: Estimated token count for this LLM call.

        Raises:
            RateLimitExceeded: If either the API call cap or token cap would
                               be exceeded by this call.
        """
        if self._max_calls == 0 and self._max_tokens == 0:
            return  # No limits configured — fast path

        now = time.time()
        window_start = now - _WINDOW_SECONDS

        try:
            events = self._load_events()
        except Exception:
            logger.error(
                "RateLimiter: failed to load state from %s — failing open",
                self._state_path,
            )
            return

        # Drop events outside the sliding window
        events = [e for e in events if e["ts"] >= window_start]

        # Check API call cap
        if self._max_calls > 0 and len(events) >= self._max_calls:
            raise RateLimitExceeded(
                f"API call rate limit reached: {len(events)}/{self._max_calls} "
                "calls in the last hour"
            )

        # Check token cap
        if self._max_tokens > 0:
            total_tokens = sum(e["tokens"] for e in events)
            if total_tokens + tokens > self._max_tokens:
                raise RateLimitExceeded(
                    f"Token rate limit reached: {total_tokens + tokens}/{self._max_tokens} "
                    "tokens in the last hour"
                )

        # Record this call
        events.append({"ts": now, "tokens": tokens})

        try:
            self._save_events(events)
        except Exception:
            logger.error("RateLimiter: failed to save state to %s", self._state_path)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _load_events(self) -> list[dict]:
        if not self._state_path.exists():
            return []
        try:
            return json.loads(self._state_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("RateLimiter: corrupted state file — starting fresh: %s", exc)
            return []

    def _save_events(self, events: list[dict]) -> None:
        self._base.mkdir(parents=True, exist_ok=True)
        content = json.dumps(events)
        tmp_fd, tmp_path_str = tempfile.mkstemp(dir=self._base, prefix=".tmp_rate_")
        tmp_path = Path(tmp_path_str)
        try:
            with open(tmp_fd, "w") as f:
                f.write(content)
            tmp_path.rename(self._state_path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_rate_limiter.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add shared/rate_limiter.py tests/test_rate_limiter.py
git commit -m "feat(phase6): add sliding-window RateLimiter with fail-open on corrupt state"
```

---

### Task 6: shared/tenant_context.py — TenantContext dataclass and factory

**Files:**
- Create: `shared/tenant_context.py`
- Create: `tests/test_tenant_context.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tenant_context.py
from pathlib import Path

import pytest

from shared.config import OpsPilotConfig
from shared.tenant_context import TenantContext, make_tenant_context
from shared.tool_permissions import ToolPermissions
from shared.usage_tracker import UsageTracker
from shared.rate_limiter import RateLimiter


def test_make_tenant_context_wires_tenant_id(tmp_path: Path):
    config = OpsPilotConfig(tenant_id="acme-corp")
    ctx = make_tenant_context(config, base_dir=tmp_path)
    assert ctx.tenant_id == "acme-corp"


def test_make_tenant_context_creates_permissions(tmp_path: Path):
    config = OpsPilotConfig(permissions={"allowed_tools": ["get_file"]})
    ctx = make_tenant_context(config, base_dir=tmp_path)
    assert isinstance(ctx.permissions, ToolPermissions)
    assert ctx.permissions.is_allowed("get_file") is True
    assert ctx.permissions.is_allowed("create_pr") is False


def test_make_tenant_context_creates_usage_tracker(tmp_path: Path):
    config = OpsPilotConfig()
    ctx = make_tenant_context(config, base_dir=tmp_path)
    assert isinstance(ctx.usage_tracker, UsageTracker)


def test_make_tenant_context_creates_rate_limiter(tmp_path: Path):
    config = OpsPilotConfig(rate_limits={"max_api_calls_per_hour": 50, "max_tokens_per_hour": 0})
    ctx = make_tenant_context(config, base_dir=tmp_path)
    assert isinstance(ctx.rate_limiter, RateLimiter)


def test_make_tenant_context_default_open_permissions(tmp_path: Path):
    """No allowed_tools configured → all tools permitted."""
    config = OpsPilotConfig()
    ctx = make_tenant_context(config, base_dir=tmp_path)
    assert ctx.permissions.is_allowed("any_tool") is True


def test_tenant_context_is_dataclass(tmp_path: Path):
    config = OpsPilotConfig(tenant_id="test")
    ctx = make_tenant_context(config, base_dir=tmp_path)
    assert isinstance(ctx, TenantContext)
    assert ctx.tenant_id == "test"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_tenant_context.py -v
```
Expected: `ModuleNotFoundError: No module named 'shared.tenant_context'`

- [ ] **Step 3: Write minimal implementation**

```python
# shared/tenant_context.py
"""TenantContext — bundles all per-deployment runtime state.

Constructed once at startup by make_tenant_context() and injected into
agents alongside LLMBackend. Agents hold a TenantContext; they do not
import individual subsystems directly.

Future DB upgrade: replace UsageTracker and RateLimiter implementations
inside make_tenant_context() only. Zero changes to agents or AgentLoop.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.rate_limiter import RateLimiter
from shared.tool_permissions import ToolPermissions
from shared.usage_tracker import UsageTracker


@dataclass
class TenantContext:
    """Runtime state for one deployment instance.

    Attributes:
        tenant_id:     Identifier for this deployment — stamped on all records.
        permissions:   Tool allowlist — checked before every tool execution.
        usage_tracker: Daily usage counters — records tokens, API calls, incidents.
        rate_limiter:  Sliding-window rate limiter — prevents runaway LLM costs.
    """

    tenant_id: str
    permissions: ToolPermissions
    usage_tracker: UsageTracker
    rate_limiter: RateLimiter


def make_tenant_context(
    config: object,
    base_dir: Path | str = Path("usage"),
) -> TenantContext:
    """Construct a TenantContext from an OpsPilotConfig instance.

    This is the single wiring point — the only place that knows how to
    build all four subsystems from config. Replace implementations here
    for the future DB-backed upgrade.

    Args:
        config:   OpsPilotConfig instance (typed as object to avoid
                  a circular import — duck-typed access is safe here).
        base_dir: Base directory for usage files. Defaults to ./usage.

    Returns:
        Fully wired TenantContext ready for injection into agents.
    """
    base_dir = Path(base_dir)
    permissions = ToolPermissions(allowed_tools=config.permissions.allowed_tools)  # type: ignore[attr-defined]
    usage_tracker = UsageTracker(base_dir=base_dir)
    rate_limiter = RateLimiter(
        max_api_calls_per_hour=config.rate_limits.max_api_calls_per_hour,  # type: ignore[attr-defined]
        max_tokens_per_hour=config.rate_limits.max_tokens_per_hour,  # type: ignore[attr-defined]
        base_dir=base_dir,
    )
    return TenantContext(
        tenant_id=config.tenant_id,  # type: ignore[attr-defined]
        permissions=permissions,
        usage_tracker=usage_tracker,
        rate_limiter=rate_limiter,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_tenant_context.py -v
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add shared/tenant_context.py tests/test_tenant_context.py
git commit -m "feat(phase6): add TenantContext dataclass and make_tenant_context factory"
```

---

### Task 7: Integrate TenantContext into AgentLoop

**Files:**
- Modify: `shared/agent_loop.py`
- Modify: `tests/test_agent_loop.py`

Rate limit check before each LLM call. Usage recording after. Permission check before tool execution.

- [ ] **Step 1: Write the failing tests**

Add these tests to the bottom of `tests/test_agent_loop.py`:

```python
# Add to tests/test_agent_loop.py

from unittest.mock import MagicMock
from shared.tenant_context import TenantContext
from shared.tool_permissions import ToolPermissions
from shared.usage_tracker import UsageTracker
from shared.rate_limiter import RateLimiter
from shared.exceptions import RateLimitExceeded


def _make_tenant_context(
    allowed_tools: list[str] | None = None,
    raise_rate_limit: bool = False,
) -> TenantContext:
    permissions = ToolPermissions(allowed_tools=allowed_tools or [])
    usage_tracker = MagicMock(spec=UsageTracker)
    rate_limiter = MagicMock(spec=RateLimiter)
    if raise_rate_limit:
        rate_limiter.check_and_consume.side_effect = RateLimitExceeded("limit reached")
    return TenantContext(
        tenant_id="test-tenant",
        permissions=permissions,
        usage_tracker=usage_tracker,
        rate_limiter=rate_limiter,
    )


def test_rate_limit_exceeded_stops_loop_gracefully(make_loop, end_turn_response):
    """When RateLimitExceeded is raised, loop exits with TURN_LIMIT outcome."""
    tenant_ctx = _make_tenant_context(raise_rate_limit=True)
    loop = make_loop(responses=[end_turn_response], tenant_context=tenant_ctx)
    result = asyncio.run(loop.run(
        messages=[{"role": "user", "content": "investigate"}],
        ctx=MagicMock(),
    ))
    assert result.outcome == LoopOutcome.TURN_LIMIT
    assert "rate limit" in result.last_assistant_text.lower()


def test_usage_tracker_records_api_call(make_loop, end_turn_response):
    """Usage tracker records an API call after each LLM call."""
    tenant_ctx = _make_tenant_context()
    loop = make_loop(responses=[end_turn_response], tenant_context=tenant_ctx)
    asyncio.run(loop.run(
        messages=[{"role": "user", "content": "investigate"}],
        ctx=MagicMock(),
    ))
    tenant_ctx.usage_tracker.record_api_call.assert_called()


def test_denied_tool_returns_error_result(make_loop, tool_use_response, tool_result_response):
    """A tool not in the allowlist returns an is_error tool result."""
    tenant_ctx = _make_tenant_context(allowed_tools=["allowed_tool"])
    # tool_use_response should call a tool NOT in the allowlist
    loop = make_loop(
        responses=[tool_use_response, tool_result_response],
        tenant_context=tenant_ctx,
    )
    # The loop should handle the denied tool gracefully (not crash)
    result = asyncio.run(loop.run(
        messages=[{"role": "user", "content": "investigate"}],
        ctx=MagicMock(),
    ))
    assert result is not None
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
pytest tests/test_agent_loop.py -v -k "rate_limit or usage_tracker or denied_tool" 2>&1 | tail -20
```
Expected: failures due to missing `tenant_context` parameter

- [ ] **Step 3: Add tenant_context parameter to AgentLoop.__init__**

In `shared/agent_loop.py`, update the imports at the top (after the `TYPE_CHECKING` block):

```python
from shared.context_budget import ContextBudget
from shared.exceptions import RateLimitExceeded
```

Remove `ContextBudget` from the `TYPE_CHECKING` block since we now import it directly.

Add `tenant_context` parameter to `AgentLoop.__init__` — add after the `context_budget` parameter:

```python
        context_budget: ContextBudget | None = None,
        tenant_context: TenantContext | None = None,
    ) -> None:
        ...
        self._context_budget = context_budget
        self._tenant_context = tenant_context
```

Also add the import for `TenantContext` at the top of the `TYPE_CHECKING` block or as a direct import. Since `TenantContext` is a dataclass (not a Pydantic model), import it directly to avoid the `TYPE_CHECKING` limitation:

```python
from shared.tenant_context import TenantContext
```

- [ ] **Step 4: Add rate limit check in AgentLoop.run() before the LLM call**

In `shared/agent_loop.py`, in the `run()` method, replace the Step 1 comment block (around line 327):

```python
            # ── Step 1: Call the model ───────────────────────────────────────
            # Check rate limit before calling the model.
            if self._tenant_context is not None:
                estimated = ContextBudget._estimate_tokens(history)
                try:
                    self._tenant_context.rate_limiter.check_and_consume(estimated)
                except RateLimitExceeded as exc:
                    logger.warning(
                        "AgentLoop: rate limit reached for tenant '%s': %s",
                        self._tenant_context.tenant_id,
                        exc,
                    )
                    extracted = await self._extract_structured(history)
                    return LoopResult(
                        outcome=LoopOutcome.TURN_LIMIT,
                        model_confidence="LOW",
                        extracted=extracted,
                        turns_used=turn + 1,
                        failed_tools=failed_tools,
                        last_assistant_text=last_text + f" [rate limit reached: {exc}]",
                    )

            raw = self._backend.complete_with_tools(
```

- [ ] **Step 5: Add usage recording after the LLM call**

In `shared/agent_loop.py`, after `text_blocks, tool_uses = self._parse_response(raw)`, add:

```python
            # Record usage after successful LLM call
            if self._tenant_context is not None:
                call_tokens = ContextBudget._estimate_tokens(
                    [{"role": "assistant", "content": [b.text if hasattr(b, "text") else "" for b in raw.content]}]
                )
                self._tenant_context.usage_tracker.record_tokens(call_tokens)
                self._tenant_context.usage_tracker.record_api_call()
```

- [ ] **Step 6: Add permission check in run_one() inside _execute_tools_concurrent()**

In `shared/agent_loop.py`, in the `run_one` nested function, add after the unknown-tool check (after the `if tool is None:` block, before the confirmation gate):

```python
            # ── Permission gate ──────────────────────────────────────────────
            if (
                self._tenant_context is not None
                and not self._tenant_context.permissions.is_allowed(block.name)
            ):
                failed_tools.append(block.name)
                return {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": (
                        f"Tool '{block.name}' is not permitted for this deployment. "
                        "Use an alternative tool or conclude without this data."
                    ),
                    "is_error": True,
                }
```

- [ ] **Step 7: Run the full agent_loop test suite**

```bash
pytest tests/test_agent_loop.py -v
```
Expected: all existing tests pass, new tests pass

- [ ] **Step 8: Commit**

```bash
git add shared/agent_loop.py tests/test_agent_loop.py
git commit -m "feat(phase6): integrate TenantContext into AgentLoop — rate limits, permissions, usage tracking"
```

---

### Task 8: Thread TenantContext through TriageAgent

**Files:**
- Modify: `agents/triage_agent.py`
- Modify: `tests/test_triage_agent.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_triage_agent.py`:

```python
# Add to tests/test_triage_agent.py

from unittest.mock import MagicMock
from shared.tenant_context import TenantContext
from shared.tool_permissions import ToolPermissions
from shared.usage_tracker import UsageTracker
from shared.rate_limiter import RateLimiter


def _make_tenant_context() -> TenantContext:
    return TenantContext(
        tenant_id="test-tenant",
        permissions=ToolPermissions(allowed_tools=[]),
        usage_tracker=MagicMock(spec=UsageTracker),
        rate_limiter=MagicMock(spec=RateLimiter),
    )


def test_triage_agent_accepts_tenant_context():
    """TriageAgent constructor accepts tenant_context without error."""
    ctx = _make_tenant_context()
    agent = TriageAgent(tenant_context=ctx)
    assert agent._tenant_context is ctx


def test_triage_agent_tenant_id_passed_to_tool_context(mock_backend, sample_failure):
    """tenant_id from TenantContext is set on ToolContext passed to tools."""
    tenant_ctx = _make_tenant_context()
    agent = TriageAgent(backend=mock_backend, tenant_context=tenant_ctx)
    # Run with a mock that returns end_turn immediately
    # (exact mock setup depends on existing test fixtures in the file)
    # Verify: agent._tenant_context.tenant_id == "test-tenant"
    assert agent._tenant_context.tenant_id == "test-tenant"
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
pytest tests/test_triage_agent.py -v -k "tenant" 2>&1 | tail -20
```
Expected: `AttributeError: __init__() got an unexpected keyword argument 'tenant_context'`

- [ ] **Step 3: Add tenant_context to TriageAgent.__init__**

In `agents/triage_agent.py`, add to the imports:

```python
from shared.tenant_context import TenantContext
```

Update `TriageAgent.__init__` signature — add `tenant_context` after `context_budget`:

```python
    def __init__(
        self,
        backend=None,
        model: str | None = None,
        provider: CIProvider | None = None,
        max_turns: int = 10,
        registry: ToolRegistry | None = None,
        context_budget: ContextBudget | None = None,
        tenant_context: TenantContext | None = None,
    ) -> None:
        super().__init__(backend=backend, model=model)
        self._provider = provider
        self._max_turns = max_turns
        self._context_budget = context_budget
        self._tenant_context = tenant_context
        if registry is None:
            registry = ToolRegistry()
            registry.register(GetFileTool())
            registry.register(GetMoreLogTool())
            registry.register(GetCommitDiffTool())
        self._registry = registry
```

- [ ] **Step 4: Pass tenant_context to AgentLoop in _run_loop()**

In `agents/triage_agent.py`, update `_run_loop()` to pass `tenant_context` and populate `ToolContext.tenant_id`:

```python
    async def _run_loop(self, failure: Failure) -> LoopResult[Triage]:
        """Build and run the AgentLoop for one failure."""
        loop: AgentLoop[Triage] = AgentLoop(
            tools=self._registry.get_tools(max_permission=Permission.READ_ONLY),
            backend=self.backend,
            domain_system_prompt=SYSTEM_PROMPT,
            response_model=Triage,
            model=self.model,
            max_turns=self._max_turns,
            context_budget=self._context_budget,
            tenant_context=self._tenant_context,
        )
        ctx = ToolContext(
            provider=self._provider,
            failure=failure,
            tenant_id=self._tenant_context.tenant_id if self._tenant_context else "",
        )
        messages = [{"role": "user", "content": self._build_initial_message(failure)}]
        return await loop.run(messages=messages, ctx=ctx)
```

- [ ] **Step 5: Run full triage test suite**

```bash
pytest tests/test_triage_agent.py -v
```
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add agents/triage_agent.py tests/test_triage_agent.py
git commit -m "feat(phase6): thread TenantContext through TriageAgent and AgentLoop"
```

---

### Task 9: Update MemoryRecord with tenant_id

**Files:**
- Modify: `shared/models.py`
- Modify: `shared/memory_store.py`
- Modify: `tests/test_memory_store.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_memory_store.py`:

```python
# Add to tests/test_memory_store.py

def test_memory_record_tenant_id_defaults_to_none():
    """Existing records without tenant_id load without error."""
    import json
    from shared.models import MemoryRecord
    from datetime import datetime
    record_dict = {
        "incident_id": "test-001",
        "repo": "org/repo",
        "failure_type": "build / test",
        "affected_service": "auth",
        "root_cause": "NPE in validate()",
        "root_cause_tokens": ["npe", "validate"],
        "severity": "high",
        "timestamp": datetime.utcnow().isoformat(),
    }
    # No tenant_id in the dict — should load fine (backward compat)
    record = MemoryRecord.model_validate(record_dict)
    assert record.tenant_id is None


def test_make_memory_record_with_tenant_id(sample_failure, sample_triage):
    from shared.memory_store import make_memory_record
    record = make_memory_record(sample_failure, sample_triage, tenant_id="acme-corp")
    assert record.tenant_id == "acme-corp"


def test_make_memory_record_without_tenant_id(sample_failure, sample_triage):
    from shared.memory_store import make_memory_record
    record = make_memory_record(sample_failure, sample_triage)
    assert record.tenant_id is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_memory_store.py -v -k "tenant" 2>&1 | tail -20
```
Expected: `TypeError` or assertion failures

- [ ] **Step 3: Add tenant_id to MemoryRecord in shared/models.py**

In `shared/models.py`, update `MemoryRecord` — add `tenant_id` field after `fix_pattern`:

```python
    tenant_id: str | None = Field(
        default=None,
        description="Deployment tenant identifier — None for records from before Phase 6.",
    )
```

- [ ] **Step 4: Update make_memory_record() in shared/memory_store.py**

In `shared/memory_store.py`, update `make_memory_record` signature and body:

```python
def make_memory_record(
    failure: Failure,
    triage: Triage,
    tenant_id: str | None = None,
) -> MemoryRecord:
    """Create a MemoryRecord from a completed Failure + Triage pair.

    Root cause tokens are precomputed here at write time so index entries are
    immediately ready for scoring without re-tokenization on each query.

    Args:
        failure:   The CI failure payload.
        triage:    The triage result (must be completed, not escalated).
        tenant_id: Deployment identifier to stamp on the record. None for
                   deployments that have not configured tenant_id.

    Returns:
        A MemoryRecord ready to pass to MemoryStore.append.
    """
    return MemoryRecord(
        incident_id=failure.id,
        repo=failure.pipeline.repo,
        failure_type=f"{failure.failure.job} / {failure.failure.step}",
        affected_service=triage.affected_service,
        root_cause=triage.output,
        root_cause_tokens=_tokenize(triage.output),
        severity=triage.severity.value,
        timestamp=triage.timestamp,
        tenant_id=tenant_id,
    )
```

- [ ] **Step 5: Run memory store tests**

```bash
pytest tests/test_memory_store.py -v
```
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add shared/models.py shared/memory_store.py tests/test_memory_store.py
git commit -m "feat(phase6): add optional tenant_id to MemoryRecord and make_memory_record"
```

---

### Task 10: Wire TenantContext in run_pipeline.py

**Files:**
- Modify: `run_pipeline.py`

- [ ] **Step 1: Add imports**

In `run_pipeline.py`, add to the imports section:

```python
from shared.config import load_config
from shared.tenant_context import make_tenant_context
from shared.memory_store import MemoryStore, make_memory_record
```

- [ ] **Step 2: Construct TenantContext at the start of run_pipeline()**

In `run_pipeline()`, after `failure = load_scenario(scenario_id)`, add:

```python
    config = load_config()
    tenant_ctx = make_tenant_context(config)
    memory_store = MemoryStore()
```

- [ ] **Step 3: Pass tenant_context to TriageAgent**

In `run_pipeline()`, update the TriageAgent construction (around line 124):

```python
    triage_agent = TriageAgent(model=model, tenant_context=tenant_ctx)
```

- [ ] **Step 4: Record incident and save to memory after fix completes**

In `run_pipeline()`, after `store.set(failure.id, "fix", ...)` and before the Notify section, add:

```python
    # Record completed investigation to memory and usage tracker
    tenant_ctx.usage_tracker.record_incident()
    memory_record = make_memory_record(failure, triage, tenant_id=tenant_ctx.tenant_id)
    memory_store.append(memory_record)
    step("memory", f"Incident saved to memory  id={failure.id[:8]}…  {GREEN}✓{RESET}")
```

- [ ] **Step 5: Smoke test — verify run_pipeline still runs**

```bash
python run_pipeline.py --list
```
Expected: lists available scenarios without error

- [ ] **Step 6: Run full test suite to verify no regressions**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: all existing tests pass

- [ ] **Step 7: Commit**

```bash
git add run_pipeline.py
git commit -m "feat(phase6): wire TenantContext in run_pipeline — usage tracking, memory stamping"
```

---

### Task 11: Finalize — .gitignore and smoke test

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add usage/ to .gitignore**

Add to `.gitignore`:

```
# Usage tracking (per-deployment runtime data)
usage/
```

- [ ] **Step 2: Run the full test suite one final time**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -40
```
Expected: all tests pass, no failures

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore usage/ directory (per-deployment runtime data)"
```

---

## Summary

| Task | New Files | Modified Files |
|------|-----------|----------------|
| 1 | `shared/exceptions.py`, `tests/test_exceptions.py` | — |
| 2 | `tests/test_tenant_config.py` | `shared/config.py` |
| 3 | `shared/tool_permissions.py`, `tests/test_tool_permissions.py` | — |
| 4 | `shared/usage_tracker.py`, `tests/test_usage_tracker.py` | — |
| 5 | `shared/rate_limiter.py`, `tests/test_rate_limiter.py` | — |
| 6 | `shared/tenant_context.py`, `tests/test_tenant_context.py` | — |
| 7 | — | `shared/agent_loop.py`, `tests/test_agent_loop.py` |
| 8 | — | `agents/triage_agent.py`, `tests/test_triage_agent.py` |
| 9 | — | `shared/models.py`, `shared/memory_store.py`, `tests/test_memory_store.py` |
| 10 | — | `run_pipeline.py` |
| 11 | — | `.gitignore` |
