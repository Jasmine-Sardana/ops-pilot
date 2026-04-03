"""Context budget management for AgentLoop.

Tracks estimated token usage across a conversation and compacts the message
history when usage approaches the model's context limit.

Compaction strategy (Strategy A):
  Replace the body of already-processed tool_result messages with a compact
  stub. The model's interpretation of those results — in the subsequent
  assistant turn — is load-bearing. The raw source data is not.

  turn N:   tool_result  → [200 lines of raw CI log]
  turn N+1: assistant    → "NPE at TokenService.validate() line 42"

  After turn N+1, the 200-line log is dead weight. The stub records that
  compaction happened so the model understands why the raw data is absent.

  Error tool results are never compacted — they are already short, and the
  model may need the error text to adapt its investigation strategy.

  The last user message in history is never compacted — it contains the most
  recent tool results which the model has not yet processed.

Token estimation:
  len(all_text_chars) // 4  — conservative heuristic, no network round-trip,
  no dependency on the LLM backend. Tends to underestimate for code and log
  content (shorter average token length), so triggering at 75% of the limit
  gives adequate headroom to absorb the heuristic error.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_MIN_THRESHOLD = 0.60   # floor: never compact at < 60% of limit
_MAX_THRESHOLD = 1.0


class ContextBudget:
    """Token budget and compaction strategy for a single AgentLoop run.

    Args:
        max_tokens:           Model context limit in tokens. Sets the ceiling
                              against which usage is measured.
        compaction_threshold: Fraction of max_tokens at which compaction
                              triggers. Default 0.75. Must be in [0.60, 1.0].
                              Lower values = more aggressive compaction.

    Raises:
        ValueError: If compaction_threshold is outside [0.60, 1.0].
    """

    def __init__(
        self,
        max_tokens: int,
        compaction_threshold: float = 0.75,
    ) -> None:
        if not (_MIN_THRESHOLD <= compaction_threshold <= _MAX_THRESHOLD):
            raise ValueError(
                f"compaction_threshold must be in [{_MIN_THRESHOLD}, {_MAX_THRESHOLD}], "
                f"got {compaction_threshold}"
            )
        self._max_tokens = max_tokens
        self._threshold = compaction_threshold
        self._trigger_at = int(max_tokens * compaction_threshold)

    @property
    def max_tokens(self) -> int:
        """The model context limit this budget was created for."""
        return self._max_tokens

    @property
    def compaction_threshold(self) -> float:
        """Fraction of max_tokens at which compaction triggers."""
        return self._threshold

    def should_compact(self, messages: list[dict]) -> bool:
        """Return True if estimated token usage meets or exceeds the trigger threshold.

        Args:
            messages: Current conversation history.

        Returns:
            True if compaction should run before the next model call.
        """
        return self._estimate_tokens(messages) >= self._trigger_at

    def compact(self, messages: list[dict]) -> list[dict]:
        """Replace processed tool_result bodies with compact stubs.

        Leaves untouched:
          - The last user message (model has not yet processed its tool results)
          - Error tool results (short; model may need the error text)
          - Assistant messages (contain the load-bearing interpretations)
          - User messages with string content (initial messages, not tool results)

        Args:
            messages: Conversation history to compact.

        Returns:
            New list with compacted tool_result blocks. The input is not mutated.
        """
        # Identify the last user message — preserve it intact
        last_user_idx: int | None = None
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user":
                last_user_idx = i
                break

        compacted: list[dict] = []
        compacted_count = 0

        for i, msg in enumerate(messages):
            # Non-user messages and the last user message pass through unchanged
            if msg.get("role") != "user" or i == last_user_idx:
                compacted.append(msg)
                continue

            content = msg.get("content", "")
            if not isinstance(content, list):
                # String-content user message (e.g. initial prompt) — pass through
                compacted.append(msg)
                continue

            new_content: list[dict] = []
            for block in content:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_result"
                    and not block.get("is_error")
                ):
                    raw_chars = len(str(block.get("content", "")))
                    new_content.append({
                        **block,
                        "content": (
                            f"[compacted: {raw_chars} chars of tool output — "
                            "key findings extracted in subsequent assistant turn]"
                        ),
                    })
                    compacted_count += 1
                else:
                    new_content.append(block)

            compacted.append({**msg, "content": new_content})

        if compacted_count:
            logger.debug(
                "ContextBudget: compacted %d tool result(s)", compacted_count
            )
        return compacted

    @staticmethod
    def _estimate_tokens(messages: list[dict]) -> int:
        """Estimate token count from total character length.

        Uses the heuristic: 1 token ≈ 4 characters (rough average for English
        prose). For code and log content, actual token density is higher, so
        this underestimates — the compaction_threshold provides the buffer.

        Args:
            messages: Conversation history (any nesting depth).

        Returns:
            Estimated token count. Always ≥ 0.
        """
        def _count_chars(obj: object) -> int:
            if isinstance(obj, str):
                return len(obj)
            if isinstance(obj, dict):
                return sum(_count_chars(v) for v in obj.values())
            if isinstance(obj, list):
                return sum(_count_chars(item) for item in obj)
            return 0  # int, bool, None — negligible

        return _count_chars(messages) // 4
