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
