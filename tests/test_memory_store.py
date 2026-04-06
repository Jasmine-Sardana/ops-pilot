"""Tests for shared/memory_store.py.

Testing strategy:
  - _tokenize and _token_jaccard are pure functions — tested exhaustively.
  - _score is pure — spot-checked for each weight component.
  - MemoryStore.append uses a tmp_path fixture so tests never touch real disk.
  - MemoryStore.retrieve_similar covers the full decision tree: empty store,
    exact match ordering, score floor, cold-start guard, top-k cap.
  - make_memory_record tests field mapping and token precomputation.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from shared.memory_store import (
    MemoryStore,
    _score,
    _token_jaccard,
    _tokenize,
    make_memory_record,
)
from shared.models import (
    DiffSummary,
    Failure,
    FailureDetail,
    MemoryRecord,
    PipelineInfo,
    Severity,
    Triage,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_record(
    incident_id: str,
    failure_type: str = "pytest / test-auth",
    affected_service: str = "auth",
    root_cause: str = "null pointer in auth tokens",
    severity: str = "high",
) -> MemoryRecord:
    from shared.memory_store import _tokenize
    return MemoryRecord(
        incident_id=incident_id,
        repo="acme/backend",
        failure_type=failure_type,
        affected_service=affected_service,
        root_cause=root_cause,
        root_cause_tokens=_tokenize(root_cause),
        severity=severity,
        timestamp=datetime(2026, 1, 1),
    )


def _make_failure() -> Failure:
    return Failure(
        id="test_failure",
        pipeline=PipelineInfo(
            provider="github_actions",
            repo="acme/backend",
            workflow="ci.yml",
            run_id="1001",
            branch="main",
            commit="abc1234",
            commit_message="feat: add tokens",
            author="dev@acme.com",
            triggered_at=datetime(2026, 1, 1),
            failed_at=datetime(2026, 1, 1),
            duration_seconds=30,
        ),
        failure=FailureDetail(
            job="test-auth",
            step="pytest",
            exit_code=1,
            log_tail=["FAILED test_auth.py::test_tokens - AttributeError: 'NoneType'"],
        ),
        diff_summary=DiffSummary(
            files_changed=["auth.py"],
            lines_added=5,
            lines_removed=3,
            key_change="removed null guard in tokens.py",
        ),
    )


def _make_triage() -> Triage:
    return Triage(
        failure_id="test_failure",
        output="Null guard removed from tokens.py causing NoneType error in auth service",
        severity=Severity.HIGH,
        affected_service="auth",
        regression_introduced_in="abc1234",
        production_impact=None,
        fix_confidence="HIGH",
        timestamp=datetime(2026, 1, 1),
    )


# ── _tokenize ─────────────────────────────────────────────────────────────────

class TestTokenize:
    def test_lowercases_text(self) -> None:
        tokens = _tokenize("NullPointerException")
        assert "nullpointerexception" in tokens

    def test_splits_on_non_alphanumeric(self) -> None:
        tokens = _tokenize("tokens.py:line")
        assert "tokens" in tokens
        assert "py" in tokens
        assert "line" in tokens

    def test_strips_stopwords(self) -> None:
        tokens = _tokenize("the null pointer in the auth service")
        assert "the" not in tokens
        assert "in" not in tokens
        assert "null" in tokens
        assert "auth" in tokens

    def test_strips_purely_numeric_tokens(self) -> None:
        tokens = _tokenize("error at line 42 port 8080")
        assert "42" not in tokens
        assert "8080" not in tokens
        assert "error" in tokens
        assert "line" in tokens

    def test_mixed_alphanumeric_kept(self) -> None:
        """Tokens like 'abc123' are kept — only purely numeric ones are stripped."""
        tokens = _tokenize("commit abc123 failed")
        assert "abc123" in tokens

    def test_empty_string_returns_empty(self) -> None:
        assert _tokenize("") == []

    def test_only_stopwords_and_numbers_returns_empty(self) -> None:
        assert _tokenize("the 42 at 8080 in") == []

    def test_file_path_splits_usefully(self) -> None:
        """tokens.py:42 should yield 'tokens' and 'py', not '42'."""
        tokens = _tokenize("tokens.py:42")
        assert tokens == ["tokens", "py"]


# ── _token_jaccard ─────────────────────────────────────────────────────────────

class TestTokenJaccard:
    def test_identical_sets_return_one(self) -> None:
        s = {"null", "pointer", "auth"}
        assert _token_jaccard(s, s) == pytest.approx(1.0)

    def test_disjoint_sets_return_zero(self) -> None:
        assert _token_jaccard({"a", "b"}, {"c", "d"}) == pytest.approx(0.0)

    def test_partial_overlap(self) -> None:
        # intersection={null}, union={null, pointer, guard} → 1/3
        a = {"null", "pointer"}
        b = {"null", "guard"}
        assert _token_jaccard(a, b) == pytest.approx(1 / 3)

    def test_both_empty_return_zero(self) -> None:
        assert _token_jaccard(set(), set()) == pytest.approx(0.0)

    def test_one_empty_returns_zero(self) -> None:
        assert _token_jaccard({"null"}, set()) == pytest.approx(0.0)
        assert _token_jaccard(set(), {"null"}) == pytest.approx(0.0)


# ── _score ─────────────────────────────────────────────────────────────────────

class TestScore:
    def test_all_match_returns_one(self) -> None:
        s = _score("a/b", "svc", {"null"}, "a/b", "svc", {"null"})
        assert s == pytest.approx(1.0)

    def test_no_match_below_floor(self) -> None:
        s = _score("a/b", "svc", {"null"}, "x/y", "other", {"unrelated"})
        assert s < 0.20

    def test_failure_type_match_only(self) -> None:
        # 1.0 / 2.0 = 0.5
        s = _score("a/b", "svc", set(), "a/b", "other", set())
        assert s == pytest.approx(0.5)

    def test_service_match_only(self) -> None:
        # 0.6 / 2.0 = 0.3
        s = _score("a/b", "svc", set(), "x/y", "svc", set())
        assert s == pytest.approx(0.3)

    def test_token_jaccard_contribution(self) -> None:
        # Only token overlap: full Jaccard on same tokens → 0.4 / 2.0 = 0.2
        s = _score("a/b", "svc", {"null"}, "x/y", "other", {"null"})
        assert s == pytest.approx(0.2)

    def test_score_normalized_max_is_one(self) -> None:
        s = _score("ft", "svc", {"x", "y"}, "ft", "svc", {"x", "y"})
        assert s <= 1.0


# ── MemoryStore.append ─────────────────────────────────────────────────────────

class TestMemoryStoreAppend:
    def test_creates_incident_file(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        store.append(_make_record("inc_001"))
        assert (tmp_path / "memory" / "incidents" / "inc_001.json").exists()

    def test_creates_index_entry(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        store.append(_make_record("inc_001"))
        index = store._load_index()
        assert len(index) == 1
        assert index[0]["incident_id"] == "inc_001"

    def test_multiple_appends_accumulate(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        store.append(_make_record("inc_001"))
        store.append(_make_record("inc_002"))
        assert len(store) == 2

    def test_reappend_same_id_is_idempotent(self, tmp_path: Path) -> None:
        """Re-appending the same incident_id replaces the old entry."""
        store = MemoryStore(tmp_path / "memory")
        store.append(_make_record("inc_001"))
        store.append(_make_record("inc_001"))
        assert len(store) == 1

    def test_index_stores_root_cause_tokens(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        store.append(_make_record("inc_001", root_cause="null pointer in auth"))
        index = store._load_index()
        assert "null" in index[0]["root_cause_tokens"]
        assert "pointer" in index[0]["root_cause_tokens"]

    def test_incident_file_roundtrips_correctly(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        original = _make_record("inc_001", root_cause="heap exhaustion in payments")
        store.append(original)
        loaded = store._load_record("inc_001")
        assert loaded is not None
        assert loaded.root_cause == original.root_cause
        assert loaded.failure_type == original.failure_type


# ── MemoryStore.retrieve_similar ──────────────────────────────────────────────

class TestMemoryStoreRetrieveSimilar:
    def test_empty_store_returns_empty_list(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        result = store.retrieve_similar("pytest / test-auth", "auth", "null pointer")
        assert result == []

    def test_exact_match_returned_first(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        store.append(_make_record(
            "exact",
            failure_type="pytest / test-auth",
            affected_service="auth",
            root_cause="null pointer in auth tokens",
        ))
        store.append(_make_record(
            "unrelated",
            failure_type="build / compile",
            affected_service="payments",
            root_cause="syntax error in payment module",
        ))
        # Add more records so we're above cold-start threshold
        for i in range(3):
            store.append(_make_record(f"other_{i}", failure_type=f"job_{i}/step",
                                       affected_service=f"svc_{i}"))
        results = store.retrieve_similar(
            "pytest / test-auth", "auth", "null pointer in auth tokens"
        )
        assert results[0].incident_id == "exact"

    def test_score_floor_filters_completely_unrelated(self, tmp_path: Path) -> None:
        """With more records than k, unrelated incidents are filtered out."""
        store = MemoryStore(tmp_path / "memory")
        # Add 5 records so cold-start doesn't apply (k defaults to 3)
        for i in range(5):
            store.append(_make_record(
                f"inc_{i}",
                failure_type=f"unique_job_{i}/step",
                affected_service=f"unique_svc_{i}",
                root_cause=f"very specific error alpha beta gamma delta {i}",
            ))
        # Query something completely different
        results = store.retrieve_similar("other/step", "other_svc", "xyz totally different zzz")
        assert results == []

    def test_cold_start_returns_without_floor(self, tmp_path: Path) -> None:
        """When store has ≤ k records, return all even if score is below 0.20."""
        store = MemoryStore(tmp_path / "memory")
        store.append(_make_record(
            "only_record",
            failure_type="job/step",
            affected_service="svc",
            root_cause="error abc",
        ))
        # Only 1 record — cold start, floor not applied
        results = store.retrieve_similar("totally/different", "other_svc", "xyz")
        assert len(results) == 1
        assert results[0].incident_id == "only_record"

    def test_returns_at_most_k_results(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        # Add 10 identical records — all score 1.0, should be capped at k=3
        for i in range(10):
            store.append(_make_record(
                f"inc_{i}",
                failure_type="pytest / test-auth",
                affected_service="auth",
                root_cause="null pointer in auth service tokens",
            ))
        results = store.retrieve_similar(
            "pytest / test-auth", "auth", "null pointer in auth service tokens", k=3
        )
        assert len(results) <= 3

    def test_results_ordered_by_descending_score(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "memory")
        # Perfect match
        store.append(_make_record(
            "perfect",
            failure_type="pytest / test-auth",
            affected_service="auth",
            root_cause="null pointer in auth service",
        ))
        # Partial match (same failure_type, different service and root cause)
        store.append(_make_record(
            "partial",
            failure_type="pytest / test-auth",
            affected_service="payments",
            root_cause="missing configuration key",
        ))
        # Add padding to exceed cold-start
        for i in range(2):
            store.append(_make_record(f"pad_{i}", failure_type=f"pad_{i}/step",
                                       affected_service=f"pad_{i}", root_cause="padding"))
        results = store.retrieve_similar(
            "pytest / test-auth", "auth", "null pointer in auth service"
        )
        # "perfect" must outrank "partial"
        ids = [r.incident_id for r in results]
        assert ids.index("perfect") < ids.index("partial")


# ── make_memory_record ─────────────────────────────────────────────────────────

class TestMakeMemoryRecord:
    def test_maps_incident_id(self) -> None:
        record = make_memory_record(_make_failure(), _make_triage())
        assert record.incident_id == "test_failure"

    def test_maps_repo(self) -> None:
        record = make_memory_record(_make_failure(), _make_triage())
        assert record.repo == "acme/backend"

    def test_maps_failure_type_as_job_step(self) -> None:
        record = make_memory_record(_make_failure(), _make_triage())
        assert record.failure_type == "test-auth / pytest"

    def test_maps_affected_service_from_triage(self) -> None:
        record = make_memory_record(_make_failure(), _make_triage())
        assert record.affected_service == "auth"

    def test_maps_root_cause_from_triage_output(self) -> None:
        record = make_memory_record(_make_failure(), _make_triage())
        assert "null guard" in record.root_cause.lower() or "null" in record.root_cause.lower()

    def test_precomputes_root_cause_tokens(self) -> None:
        record = make_memory_record(_make_failure(), _make_triage())
        assert isinstance(record.root_cause_tokens, list)
        assert len(record.root_cause_tokens) > 0

    def test_strips_numeric_tokens_from_root_cause(self) -> None:
        triage = Triage(
            failure_id="test",
            output="NullPointerException at line 42 in tokens.py",
            severity=Severity.HIGH,
            affected_service="auth",
            regression_introduced_in="abc123",
            fix_confidence="HIGH",
            timestamp=datetime(2026, 1, 1),
        )
        record = make_memory_record(_make_failure(), triage)
        assert "42" not in record.root_cause_tokens
        assert "nullpointerexception" in record.root_cause_tokens
        assert "tokens" in record.root_cause_tokens

    def test_maps_severity_as_string(self) -> None:
        record = make_memory_record(_make_failure(), _make_triage())
        assert record.severity == "high"

    def test_fix_pattern_defaults_to_none(self) -> None:
        record = make_memory_record(_make_failure(), _make_triage())
        assert record.fix_pattern is None


# ── tenant_id support ─────────────────────────────────────────────────────────

class TestTenantId:
    def test_memory_record_tenant_id_defaults_to_none(self) -> None:
        """Existing records without tenant_id load without error (backward compat)."""
        from datetime import datetime
        record_dict = {
            "incident_id": "test-001",
            "repo": "org/repo",
            "failure_type": "build / test",
            "affected_service": "auth",
            "root_cause": "NPE in validate()",
            "root_cause_tokens": ["npe", "validate"],
            "severity": "high",
            "timestamp": datetime.utcnow().isoformat(),
        }
        record = MemoryRecord.model_validate(record_dict)
        assert record.tenant_id is None

    def test_make_memory_record_with_tenant_id(self) -> None:
        record = make_memory_record(_make_failure(), _make_triage(), tenant_id="acme-corp")
        assert record.tenant_id == "acme-corp"

    def test_make_memory_record_without_tenant_id(self) -> None:
        record = make_memory_record(_make_failure(), _make_triage())
        assert record.tenant_id is None

    def test_memory_record_with_tenant_id_round_trips(self, tmp_path) -> None:
        """tenant_id survives a write-read cycle through MemoryStore."""
        store = MemoryStore(base_dir=tmp_path)
        record = make_memory_record(_make_failure(), _make_triage(), tenant_id="acme-corp")
        store.append(record)
        retrieved = store._load_record(record.incident_id)
        assert retrieved is not None
        assert retrieved.tenant_id == "acme-corp"
