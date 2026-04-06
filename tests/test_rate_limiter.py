# tests/test_rate_limiter.py
import json
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
    old_ts = time.time() - 3700  # older than 1 hour
    state_path = tmp_path / "rate_state.json"
    state_path.write_text(json.dumps([
        {"ts": old_ts, "tokens": 10},
        {"ts": old_ts, "tokens": 10},
    ]))
    # Old events are expired, so first two calls should pass
    limiter.check_and_consume(tokens=10)
    limiter.check_and_consume(tokens=10)
    # Third call exceeds cap=2 (two fresh events now in window)
    with pytest.raises(RateLimitExceeded):
        limiter.check_and_consume(tokens=10)


def test_corrupt_state_file_fails_open(tmp_path: Path):
    """Corrupted state file means fail-open — RateLimitExceeded is NOT raised."""
    limiter = RateLimiter(max_api_calls_per_hour=1, max_tokens_per_hour=0, base_dir=tmp_path)
    state_path = tmp_path / "rate_state.json"
    state_path.write_text("{{not valid json")
    # Should not raise — fail-open on corrupt state
    limiter.check_and_consume(tokens=10)
