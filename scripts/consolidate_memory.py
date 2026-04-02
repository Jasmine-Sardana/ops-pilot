#!/usr/bin/env python3
"""ops-pilot weekly memory consolidation job.

Groups past incidents by failure_type + affected_service. For groups with
enough incidents (default: ≥ 3), calls an LLM to extract a concise, durable
fix_pattern string and writes it back to each incident's record.

The fix_pattern is then available to CoordinatorAgent via memory retrieval —
it appears in the coordinator's prior_incidents block and helps workers skip
investigation steps they've already solved before.

A consolidated index is also written to memory/consolidated.json for
inspection and auditing.

Usage::

    python3 scripts/consolidate_memory.py
    python3 scripts/consolidate_memory.py --min-incidents 5
    python3 scripts/consolidate_memory.py --memory-dir /path/to/memory
    python3 scripts/consolidate_memory.py --dry-run   # print groups, no writes
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from shared.config import load_config
from shared.llm_backend import make_backend
from shared.memory_store import MemoryRecord, MemoryStore, _atomic_write

logger = logging.getLogger("ops-pilot.consolidate")

_CONSOLIDATION_SYSTEM = (
    "You are a senior SRE summarizing recurring CI failure patterns. "
    "Be concise and precise — one sentence, active voice, no hedging."
)


def consolidate(
    memory_store: MemoryStore,
    backend,
    model: str,
    min_incidents: int = 3,
    dry_run: bool = False,
) -> dict[str, str]:
    """Extract durable fix patterns for recurring failure groups.

    Args:
        memory_store:   The MemoryStore instance to read and update.
        backend:        LLM backend for pattern extraction.
        model:          Model ID to use.
        min_incidents:  Minimum group size before consolidation runs.
        dry_run:        If True, print groups but do not write anything.

    Returns:
        Dict mapping "{failure_type} | {affected_service}" to extracted pattern.
    """
    index = memory_store._load_index()
    if not index:
        print("No incidents in memory — nothing to consolidate.")
        return {}

    # Group incident IDs by failure_type + affected_service
    groups: dict[str, list[str]] = defaultdict(list)
    for entry in index:
        key = f"{entry['failure_type']} | {entry['affected_service']}"
        groups[key].append(entry["incident_id"])

    qualifying = {k: v for k, v in groups.items() if len(v) >= min_incidents}
    print(
        f"  Total incidents: {len(index)}\n"
        f"  Groups found:    {len(groups)}\n"
        f"  Qualifying (≥{min_incidents}): {len(qualifying)}\n"
    )

    if not qualifying:
        print("No groups meet the minimum incident threshold.")
        return {}

    patterns: dict[str, str] = {}

    for group_key, incident_ids in qualifying.items():
        records = [memory_store._load_record(iid) for iid in incident_ids]
        records = [r for r in records if r is not None]
        if not records:
            continue

        failure_type, affected_service = group_key.split(" | ", 1)
        root_causes = "\n".join(f"- {r.root_cause}" for r in records)
        prompt = (
            f"These {len(records)} CI incidents all share:\n"
            f"  failure_type: {failure_type}\n"
            f"  affected_service: {affected_service}\n\n"
            f"Observed root causes:\n{root_causes}\n\n"
            "In one concise sentence, what is the recurring fix pattern for this type of failure?"
        )

        if dry_run:
            print(f"  [dry-run] Would consolidate: {group_key} ({len(records)} incidents)")
            continue

        pattern = backend.complete(
            system=_CONSOLIDATION_SYSTEM,
            user=prompt,
            model=model,
            max_tokens=150,
        ).strip()
        patterns[group_key] = pattern
        print(f"  {group_key}:\n    → {pattern}\n")

        # Write fix_pattern back to each incident record
        for record in records:
            updated = record.model_copy(update={"fix_pattern": pattern})
            incident_path = memory_store._incidents_dir / f"{record.incident_id}.json"
            _atomic_write(incident_path, updated.model_dump_json(indent=2))

    if patterns and not dry_run:
        out_path = memory_store._base / "consolidated.json"
        _atomic_write(out_path, json.dumps(patterns, indent=2))
        print(f"Consolidated index written to {out_path}")

    return patterns


def main() -> None:
    parser = argparse.ArgumentParser(description="ops-pilot memory consolidation")
    parser.add_argument("--config", help="Path to ops-pilot.yml")
    parser.add_argument(
        "--memory-dir",
        default="memory",
        help="Memory directory (default: memory)",
    )
    parser.add_argument(
        "--min-incidents",
        type=int,
        default=3,
        help="Minimum incidents per group to trigger consolidation (default: 3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print groups without writing anything",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    cfg = load_config(args.config)
    backend = make_backend(cfg)
    memory_store = MemoryStore(Path(args.memory_dir))

    print("ops-pilot memory consolidation")
    print(f"  Memory dir:    {args.memory_dir}")
    print(f"  Min incidents: {args.min_incidents}")
    print(f"  Dry run:       {args.dry_run}\n")

    patterns = consolidate(
        memory_store=memory_store,
        backend=backend,
        model=cfg.model,
        min_incidents=args.min_incidents,
        dry_run=args.dry_run,
    )

    print(f"\n{len(patterns)} pattern(s) consolidated.")


if __name__ == "__main__":
    main()
