"""Custom exceptions for ops-pilot tenant enforcement."""


class RateLimitExceeded(Exception):
    """Raised when a deployment's per-hour rate limit cap is reached."""


class ToolPermissionDenied(Exception):
    """Raised when an agent attempts to use a tool not in its allowlist."""
