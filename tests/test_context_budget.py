"""Tests for shared/context_budget.py.

Testing strategy:
  - _estimate_tokens is a pure static method — tested exhaustively across all
    message content structures (string, list, nested dict).
  - should_compact is a pure function of estimate vs threshold — tested at the
    boundary exactly.
  - compact covers all the structural cases: non-user messages unchanged,
    last user message preserved, earlier tool_results compacted, error results
    preserved, string-content user messages pass through.
  - Constructor validation tests the threshold floor.
  - Integration: AgentLoop tests verify that the budget is invoked at the right
    point in the loop lifecycle and that None budget leaves existing behaviour
    unchanged.
"""

from __future__ import annotations

import pytest

from shared.context_budget import ContextBudget

# ── Helpers ────────────────────────────────────────────────────────────────────

def _tool_result_msg(content: str, is_error: bool = False) -> dict:
    block: dict = {"type": "tool_result", "tool_use_id": "toolu_01", "content": content}
    if is_error:
        block["is_error"] = True
    return {"role": "user", "content": [block]}


def _assistant_msg(text: str) -> dict:
    return {"role": "assistant", "content": [{"type": "text", "text": text}]}


def _initial_user_msg(text: str) -> dict:
    return {"role": "user", "content": text}


# ── _estimate_tokens ───────────────────────────────────────────────────────────

class TestEstimateTokens:
    def test_empty_list_returns_zero(self) -> None:
        assert ContextBudget._estimate_tokens([]) == 0

    def test_string_content_message(self) -> None:
        # 400 chars of content + small overhead from "role"/"user" keys = ~101 tokens
        msgs = [{"role": "user", "content": "a" * 400}]
        estimate = ContextBudget._estimate_tokens(msgs)
        assert 100 <= estimate <= 105

    def test_list_content_text_block(self) -> None:
        # 800 chars of text + small overhead from role/type strings = ~203 tokens
        msgs = [{"role": "assistant", "content": [{"type": "text", "text": "a" * 800}]}]
        estimate = ContextBudget._estimate_tokens(msgs)
        assert 200 <= estimate <= 210

    def test_tool_result_block_counted(self) -> None:
        msgs = [_tool_result_msg("a" * 4000)]
        # content key contributes 4000 chars, so 1000 tokens minimum
        assert ContextBudget._estimate_tokens(msgs) >= 1000

    def test_multiple_messages_summed(self) -> None:
        msgs = [
            _initial_user_msg("a" * 400),   # 100 tokens
            _assistant_msg("b" * 400),       # 100 tokens
        ]
        estimate = ContextBudget._estimate_tokens(msgs)
        # Must be at least 200 (the two content strings)
        assert estimate >= 200

    def test_deeply_nested_dict_counted(self) -> None:
        msgs = [{"role": "user", "content": [{"type": "tool_use", "input": {"key": "a" * 400}}]}]
        assert ContextBudget._estimate_tokens(msgs) >= 100

    def test_non_string_values_ignored(self) -> None:
        """Ints, bools, None in dicts contribute 0."""
        msgs = [{"role": "user", "content": [{"type": "tool_result", "is_error": False, "content": ""}]}]
        # Should not raise, and should return a non-negative value
        assert ContextBudget._estimate_tokens(msgs) >= 0


# ── should_compact ─────────────────────────────────────────────────────────────

class TestShouldCompact:
    def test_below_threshold_returns_false(self) -> None:
        budget = ContextBudget(max_tokens=1000, compaction_threshold=0.75)
        # trigger at 750 tokens; 400 chars / 4 = 100 tokens
        msgs = [_initial_user_msg("a" * 400)]
        assert budget.should_compact(msgs) is False

    def test_at_threshold_returns_true(self) -> None:
        budget = ContextBudget(max_tokens=100, compaction_threshold=0.75)
        # trigger at 75 tokens; exactly 300 chars = 75 tokens
        msgs = [_initial_user_msg("a" * 300)]
        assert budget.should_compact(msgs) is True

    def test_above_threshold_returns_true(self) -> None:
        budget = ContextBudget(max_tokens=100, compaction_threshold=0.75)
        msgs = [_initial_user_msg("a" * 400)]  # 100 tokens > 75 trigger
        assert budget.should_compact(msgs) is True

    def test_empty_messages_never_compacts(self) -> None:
        budget = ContextBudget(max_tokens=100, compaction_threshold=0.75)
        assert budget.should_compact([]) is False


# ── compact ────────────────────────────────────────────────────────────────────

class TestCompact:
    def test_replaces_tool_result_content_with_stub(self) -> None:
        budget = ContextBudget(max_tokens=1000)
        history = [
            _initial_user_msg("investigate this"),
            _assistant_msg("calling tool"),
            _tool_result_msg("a" * 500),   # first user msg — should be compacted
            _assistant_msg("found root cause"),
            _tool_result_msg("b" * 500),   # last user msg — should NOT be compacted
        ]
        result = budget.compact(history)
        # Third message (index 2) — first tool result — should be compacted
        compacted_block = result[2]["content"][0]
        assert "[compacted:" in compacted_block["content"]
        assert "500" in compacted_block["content"]

    def test_preserves_last_user_message_intact(self) -> None:
        budget = ContextBudget(max_tokens=1000)
        raw_content = "b" * 500
        history = [
            _tool_result_msg("a" * 500),   # earlier — compacted
            _tool_result_msg(raw_content),  # last — preserved
        ]
        result = budget.compact(history)
        last_block = result[-1]["content"][0]
        assert last_block["content"] == raw_content  # unchanged

    def test_preserves_error_tool_results(self) -> None:
        budget = ContextBudget(max_tokens=1000)
        error_content = "Tool failed: connection refused"
        history = [
            _initial_user_msg("start"),
            _assistant_msg("calling tool"),
            _tool_result_msg(error_content, is_error=True),  # error — preserved even if not last
            _assistant_msg("handling error"),
            _tool_result_msg("x" * 500),  # last user msg
        ]
        result = budget.compact(history)
        # Error result at index 2 — must be preserved
        error_block = result[2]["content"][0]
        assert error_block["content"] == error_content

    def test_preserves_assistant_messages(self) -> None:
        budget = ContextBudget(max_tokens=1000)
        assistant_text = "Root cause: null pointer at line 42"
        history = [
            _tool_result_msg("a" * 500),
            _assistant_msg(assistant_text),
            _tool_result_msg("b" * 500),
        ]
        result = budget.compact(history)
        assert result[1]["content"][0]["text"] == assistant_text

    def test_string_content_user_message_passes_through(self) -> None:
        """Initial user message with string content is never modified."""
        budget = ContextBudget(max_tokens=1000)
        text = "investigate this failure"
        history = [
            _initial_user_msg(text),
            _tool_result_msg("b" * 500),
        ]
        result = budget.compact(history)
        assert result[0]["content"] == text

    def test_multiple_tool_results_all_but_last_compacted(self) -> None:
        budget = ContextBudget(max_tokens=1000)
        history = [
            _tool_result_msg("first call result"),
            _assistant_msg("thinking..."),
            _tool_result_msg("second call result"),
            _assistant_msg("thinking more..."),
            _tool_result_msg("third call result"),  # last — preserved
        ]
        result = budget.compact(history)
        assert "[compacted:" in result[0]["content"][0]["content"]
        assert "[compacted:" in result[2]["content"][0]["content"]
        assert result[4]["content"][0]["content"] == "third call result"

    def test_input_list_not_mutated(self) -> None:
        budget = ContextBudget(max_tokens=1000)
        history = [
            _tool_result_msg("a" * 500),
            _tool_result_msg("b" * 500),
        ]
        original_content = history[0]["content"][0]["content"]
        budget.compact(history)
        # Original must be unchanged
        assert history[0]["content"][0]["content"] == original_content

    def test_empty_history_returns_empty(self) -> None:
        budget = ContextBudget(max_tokens=1000)
        assert budget.compact([]) == []

    def test_single_user_message_preserved(self) -> None:
        """Single message is the 'last user message' — never compacted."""
        budget = ContextBudget(max_tokens=1000)
        history = [_tool_result_msg("only message")]
        result = budget.compact(history)
        assert result[0]["content"][0]["content"] == "only message"

    def test_compaction_reduces_token_estimate(self) -> None:
        """After compaction, estimated tokens should be lower."""
        budget = ContextBudget(max_tokens=1000)
        history = [
            _tool_result_msg("a" * 2000),
            _assistant_msg("found it"),
            _tool_result_msg("b" * 2000),  # last — preserved
        ]
        before = ContextBudget._estimate_tokens(history)
        compacted = budget.compact(history)
        after = ContextBudget._estimate_tokens(compacted)
        assert after < before


# ── Constructor validation ─────────────────────────────────────────────────────

class TestConstructorValidation:
    def test_valid_threshold_accepted(self) -> None:
        budget = ContextBudget(max_tokens=200_000, compaction_threshold=0.75)
        assert budget.compaction_threshold == 0.75

    def test_minimum_threshold_accepted(self) -> None:
        ContextBudget(max_tokens=100_000, compaction_threshold=0.60)  # no error

    def test_maximum_threshold_accepted(self) -> None:
        ContextBudget(max_tokens=100_000, compaction_threshold=1.0)  # no error

    def test_below_minimum_raises(self) -> None:
        with pytest.raises(ValueError, match="compaction_threshold"):
            ContextBudget(max_tokens=100_000, compaction_threshold=0.59)

    def test_above_maximum_raises(self) -> None:
        with pytest.raises(ValueError, match="compaction_threshold"):
            ContextBudget(max_tokens=100_000, compaction_threshold=1.01)

    def test_properties_accessible(self) -> None:
        budget = ContextBudget(max_tokens=50_000, compaction_threshold=0.80)
        assert budget.max_tokens == 50_000
        assert budget.compaction_threshold == 0.80


# ── AgentLoop integration ──────────────────────────────────────────────────────

class TestAgentLoopIntegration:
    """Verify ContextBudget is invoked at the right point in AgentLoop.run()."""

    def _make_end_turn_response(self, text: str = "done"):
        import types
        block = types.SimpleNamespace(type="text", text=text)
        return types.SimpleNamespace(content=[block])

    def _make_backend(self, responses):
        from unittest.mock import MagicMock
        backend = MagicMock()
        backend.complete_with_tools.side_effect = responses
        backend.complete.return_value = '{"output": "done", "severity": "low", "affected_service": "auth", "regression_introduced_in": "abc", "fix_confidence": "HIGH"}'
        return backend

    def test_no_budget_loop_runs_normally(self) -> None:
        """context_budget=None leaves existing loop behaviour unchanged."""
        from unittest.mock import MagicMock

        from shared.agent_loop import AgentLoop, ToolContext
        from shared.models import Triage

        backend = self._make_backend([self._make_end_turn_response()])
        loop: AgentLoop[Triage] = AgentLoop(
            tools=[],
            backend=backend,
            domain_system_prompt="test",
            response_model=Triage,
            model="test-model",
            context_budget=None,
        )
        import asyncio
        ctx = ToolContext(provider=None, failure=MagicMock())
        result = asyncio.run(loop.run(messages=[{"role": "user", "content": "go"}], ctx=ctx))
        assert result.turns_used == 1

    def test_budget_triggers_compaction_when_threshold_met(self) -> None:
        """When budget.should_compact returns True, compact() is applied."""
        import asyncio
        from unittest.mock import MagicMock, patch

        from shared.agent_loop import AgentLoop, ToolContext
        from shared.models import Triage

        backend = self._make_backend([self._make_end_turn_response()])
        # Budget that always triggers
        budget = ContextBudget(max_tokens=1, compaction_threshold=0.60)

        with patch.object(ContextBudget, "should_compact", return_value=True) as mock_should, \
             patch.object(ContextBudget, "compact", wraps=budget.compact) as mock_compact:
            loop: AgentLoop[Triage] = AgentLoop(
                tools=[],
                backend=backend,
                domain_system_prompt="test",
                response_model=Triage,
                model="test-model",
                context_budget=budget,
            )
            ctx = ToolContext(provider=None, failure=MagicMock())
            asyncio.run(loop.run(messages=[{"role": "user", "content": "go"}], ctx=ctx))

        mock_should.assert_called()
        mock_compact.assert_called()

    def test_budget_not_applied_when_below_threshold(self) -> None:
        """When budget.should_compact returns False, compact() is not called."""
        import asyncio
        from unittest.mock import MagicMock, patch

        from shared.agent_loop import AgentLoop, ToolContext
        from shared.models import Triage

        backend = self._make_backend([self._make_end_turn_response()])
        budget = ContextBudget(max_tokens=200_000, compaction_threshold=0.75)

        with patch.object(ContextBudget, "compact", wraps=budget.compact) as mock_compact:
            loop: AgentLoop[Triage] = AgentLoop(
                tools=[],
                backend=backend,
                domain_system_prompt="test",
                response_model=Triage,
                model="test-model",
                context_budget=budget,
            )
            ctx = ToolContext(provider=None, failure=MagicMock())
            asyncio.run(loop.run(messages=[{"role": "user", "content": "short message"}], ctx=ctx))

        mock_compact.assert_not_called()
