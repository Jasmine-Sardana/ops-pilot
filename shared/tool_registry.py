"""Tool registry for ops-pilot agent loops.

Central catalog of all available tools with permission-tier filtering.
Agents query the registry at construction time to get a tool list scoped to
their blast-radius ceiling — TriageAgent asks for READ_ONLY, FixAgent for WRITE.

The registry answers one question: given a permission ceiling, which tools
are appropriate for this agent? It does not own execution or confirmation logic.
Those responsibilities stay in AgentLoop.

Permission model:
  - READ_ONLY and WRITE form a linear watermark tier (READ_ONLY ≤ WRITE).
  - DANGEROUS and REQUIRES_CONFIRMATION are outside the linear tier. They are
    excluded by default and require explicit opt-in via include_dangerous=True.
    Even when included, REQUIRES_CONFIRMATION tools are still blocked at
    execution time unless AgentLoop is constructed with a confirmation hook.
"""

from __future__ import annotations

from shared.agent_loop import Permission, Tool

# Linear tier ordering for the watermark filter.
# Only READ_ONLY and WRITE participate — DANGEROUS and REQUIRES_CONFIRMATION
# are outside this ordering and handled separately.
_TIER_ORDER: dict[Permission, int] = {
    Permission.READ_ONLY: 0,
    Permission.WRITE: 1,
}


class ToolRegistry:
    """Central catalog of available tools, queryable by permission tier.

    Tools are registered at startup and retrieved by agents at construction
    time. The registry does not mutate after population.

    Example usage::

        registry = ToolRegistry()
        registry.register(GetFileTool())
        registry.register(UpdateFileTool())

        # Triage agent — read only
        triage_tools = registry.get_tools(max_permission=Permission.READ_ONLY)

        # Fix agent — can also write
        fix_tools = registry.get_tools(max_permission=Permission.WRITE)
    """

    def __init__(self) -> None:
        # Ordered dict preserves registration order, which becomes tool list
        # order. Consistent ordering helps with deterministic test assertions.
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Add a tool to the registry.

        Args:
            tool: Tool instance to register.

        Raises:
            ValueError: If a tool with the same name is already registered.
                        Duplicate names would silently shadow tools otherwise.
        """
        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered. "
                "Use a distinct name or deregister the existing tool first."
            )
        self._tools[tool.name] = tool

    def get_tools(
        self,
        max_permission: Permission = Permission.READ_ONLY,
        include_dangerous: bool = False,
    ) -> list[Tool]:
        """Return tools that fit within the given permission ceiling.

        The watermark applies only to the READ_ONLY / WRITE tier. DANGEROUS and
        REQUIRES_CONFIRMATION tools are orthogonally gated by include_dangerous.

        Args:
            max_permission:   Highest tier to include. READ_ONLY → read tools
                              only. WRITE → read + write tools.
            include_dangerous: If True, also include DANGEROUS and
                               REQUIRES_CONFIRMATION tools. These are excluded
                               by default. Note that REQUIRES_CONFIRMATION tools
                               will still be blocked at execution time if
                               AgentLoop has no confirmation hook wired.

        Returns:
            List of matching tools in registration order.
        """
        max_tier = _TIER_ORDER.get(max_permission, 0)
        result: list[Tool] = []
        for tool in self._tools.values():
            tier = _TIER_ORDER.get(tool.permission)
            if tier is not None:
                # Tiered tool: include only if within the watermark ceiling
                if tier <= max_tier:
                    result.append(tool)
            elif include_dangerous:
                # Non-tiered (DANGEROUS / REQUIRES_CONFIRMATION): opt-in only
                result.append(tool)
        return result

    def all_tool_names(self) -> list[str]:
        """Return all registered tool names regardless of permission tier.

        Useful for logging and diagnostics.
        """
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)
