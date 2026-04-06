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
