# tests/test_tool_permissions.py
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
