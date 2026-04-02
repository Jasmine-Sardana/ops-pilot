"""Memory store for ops-pilot — persists incident records and retrieves similar past failures.

Storage layout::

    memory/
        incidents/                 ← one JSON file per incident
            <incident-id>.json
        index.json                 ← scoring metadata for all incidents

Similarity scoring uses structured weighted similarity over typed Triage fields::

    score = (
        1.0 * exact_match(failure_type)
        + 0.6 * exact_match(affected_service)
        + 0.4 * token_jaccard(root_cause_tokens)
    ) / 2.0   ← normalized to [0, 1]

All writes use POSIX atomic rename (same pattern as task_queue.py) — no partial writes.
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
from pathlib import Path

from pydantic import BaseModel

from shared.models import Failure, MemoryRecord, Triage

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

_STOPWORDS = frozenset({
    "a", "an", "and", "at", "be", "by", "for", "from",
    "in", "is", "it", "not", "of", "on", "or", "that",
    "the", "this", "to", "was", "with",
})

_MAX_SCORE = 2.0        # 1.0 + 0.6 + 0.4
_SCORE_FLOOR = 0.20     # normalized minimum — filters noise when corpus is large enough


# ── Tokenization ──────────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Tokenize text for similarity comparison.

    Lowercases, splits on non-alphanumeric boundaries, then strips:
    - stopwords (carry no signal)
    - purely numeric tokens (line numbers, ports, timestamps diverge across
      incidents without contributing meaningful signal)
    """
    raw = re.split(r"[^a-zA-Z0-9]+", text.lower())
    return [t for t in raw if t and not t.isdigit() and t not in _STOPWORDS]


def _token_jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two token sets. Returns 0.0 for empty inputs."""
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


# ── Internal scoring ───────────────────────────────────────────────────────────

def _score(
    entry_ft: str,
    entry_svc: str,
    entry_tokens: set[str],
    query_ft: str,
    query_svc: str,
    query_tokens: set[str],
) -> float:
    """Compute normalized weighted similarity score in [0, 1].

    Weights:
        1.0 — failure_type exact match (highest signal: same job/step pattern)
        0.6 — affected_service exact match (medium signal: same service)
        0.4 — root_cause token Jaccard (medium signal: similar error vocabulary)
    """
    raw = (
        1.0 * (entry_ft == query_ft)
        + 0.6 * (entry_svc == query_svc)
        + 0.4 * _token_jaccard(entry_tokens, query_tokens)
    )
    return raw / _MAX_SCORE


# ── Index entry (internal) ────────────────────────────────────────────────────

class _IndexEntry(BaseModel):
    """Scoring metadata stored in index.json.

    Contains everything needed for similarity scoring — avoids loading full
    incident files during retrieve_similar.
    """

    incident_id: str
    failure_type: str
    affected_service: str
    root_cause_tokens: list[str]
    severity: str
    timestamp: str  # ISO format string


# ── MemoryStore ───────────────────────────────────────────────────────────────

class MemoryStore:
    """Append-only store for incident records with weighted similarity retrieval.

    Args:
        base_dir: Root directory for memory storage. Defaults to ./memory.
                  Created on first write if it does not exist.
    """

    def __init__(self, base_dir: Path | str = Path("memory")) -> None:
        self._base = Path(base_dir)
        self._incidents_dir = self._base / "incidents"
        self._index_path = self._base / "index.json"

    def append(self, record: MemoryRecord) -> None:
        """Persist an incident record and update the similarity index.

        Both the incident file and the index update use POSIX atomic rename —
        no partial writes are possible. The index is updated last; if the
        process dies between the two writes, the incident file exists but is
        not indexed (harmless — the next consolidation run can rebuild it).

        Re-appending an existing incident_id is idempotent: the old entry is
        replaced in the index and the incident file is overwritten.

        Args:
            record: The incident to persist.
        """
        self._incidents_dir.mkdir(parents=True, exist_ok=True)

        # Write incident file atomically
        incident_path = self._incidents_dir / f"{record.incident_id}.json"
        _atomic_write(incident_path, record.model_dump_json(indent=2))

        # Load index, remove any existing entry with the same ID, append new entry
        entries = self._load_index()
        entries = [e for e in entries if e["incident_id"] != record.incident_id]
        entries.append(
            _IndexEntry(
                incident_id=record.incident_id,
                failure_type=record.failure_type,
                affected_service=record.affected_service,
                root_cause_tokens=record.root_cause_tokens,
                severity=record.severity,
                timestamp=record.timestamp.isoformat(),
            ).model_dump()
        )
        _atomic_write(self._index_path, json.dumps(entries, indent=2))
        logger.debug(
            "MemoryStore: appended %s (index now has %d entries)",
            record.incident_id,
            len(entries),
        )

    def retrieve_similar(
        self,
        failure_type: str,
        affected_service: str,
        root_cause: str,
        k: int = 3,
    ) -> list[MemoryRecord]:
        """Retrieve the k most similar past incidents.

        Applies a normalized score floor of 0.20 unless the index has fewer
        than k entries (cold-start guard — return whatever exists rather than
        never building signal for the first few incidents).

        Args:
            failure_type:     "{job} / {step}" of the incoming failure.
            affected_service: Best-effort service name proxy (e.g. job name).
            root_cause:       Text to tokenize for Jaccard comparison (e.g.
                              log tail + diff key_change of the incoming failure).
            k:                Maximum number of records to return.

        Returns:
            List of MemoryRecord ordered by descending similarity score.
            Empty if the index is empty or all records score below floor.
        """
        entries = self._load_index()
        if not entries:
            return []

        query_tokens = set(_tokenize(root_cause))
        cold_start = len(entries) <= k

        scored: list[tuple[float, str]] = []
        for entry in entries:
            s = _score(
                entry_ft=entry["failure_type"],
                entry_svc=entry["affected_service"],
                entry_tokens=set(entry["root_cause_tokens"]),
                query_ft=failure_type,
                query_svc=affected_service,
                query_tokens=query_tokens,
            )
            if cold_start or s >= _SCORE_FLOOR:
                scored.append((s, entry["incident_id"]))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:k]

        records: list[MemoryRecord] = []
        for _, incident_id in top:
            record = self._load_record(incident_id)
            if record is not None:
                records.append(record)
        return records

    def _load_index(self) -> list[dict]:
        """Load the index from disk. Returns empty list on missing or corrupt file."""
        if not self._index_path.exists():
            return []
        try:
            return json.loads(self._index_path.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning("MemoryStore: corrupted index at %s — returning empty", self._index_path)
            return []

    def _load_record(self, incident_id: str) -> MemoryRecord | None:
        """Load a single incident record from disk."""
        path = self._incidents_dir / f"{incident_id}.json"
        if not path.exists():
            logger.warning("MemoryStore: incident file missing for %s", incident_id)
            return None
        try:
            return MemoryRecord.model_validate_json(path.read_text())
        except Exception:
            logger.warning("MemoryStore: corrupted incident record %s — skipping", incident_id)
            return None

    def __len__(self) -> int:
        """Number of indexed incidents."""
        return len(self._load_index())


# ── Atomic write helper ────────────────────────────────────────────────────────

def _atomic_write(path: Path, content: str) -> None:
    """Write content to path via an atomic rename.

    Uses tempfile.mkstemp in the same directory as the target so the rename
    is always within a single filesystem (POSIX rename guarantee).

    Args:
        path:    Target file path. Parent directory must already exist.
        content: Text content to write.
    """
    tmp_fd, tmp_path_str = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
    tmp_path = Path(tmp_path_str)
    try:
        with open(tmp_fd, "w") as f:
            f.write(content)
        tmp_path.rename(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


# ── Factory helper ────────────────────────────────────────────────────────────

def make_memory_record(failure: Failure, triage: Triage) -> MemoryRecord:
    """Create a MemoryRecord from a completed Failure + Triage pair.

    Root cause tokens are precomputed here at write time so index entries are
    immediately ready for scoring without re-tokenization on each query.

    Args:
        failure: The CI failure payload.
        triage:  The triage result (must be completed, not escalated).

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
    )
