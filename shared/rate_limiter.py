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
        """Load events from state file. Returns empty list on missing/corrupt file."""
        if not self._state_path.exists():
            return []
        try:
            return json.loads(self._state_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("RateLimiter: corrupted state file — starting fresh: %s", exc)
            return []

    def _save_events(self, events: list[dict]) -> None:
        """Write events to state file atomically."""
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
