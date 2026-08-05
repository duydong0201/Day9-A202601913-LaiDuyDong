"""Batch execution for submitted cases; no synthetic cases or evidence are created."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .case_io import read_case, write_json
from .coordinator import CoordinatorAgent
from .repository import OlistRepository


class BatchRunner:
    def __init__(self, data_dir: Path, input_dir: Path, output_dir: Path, trace_path: Path) -> None:
        self.data_dir = data_dir
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.trace_path = trace_path

    def run(self, require_50_cases: bool = True) -> int:
        paths = sorted(self.input_dir.glob("EC_*.json"))
        expected_names = {f"EC_{number:03d}.json" for number in range(1, 51)}
        actual_names = {path.name for path in paths}
        if require_50_cases and actual_names != expected_names:
            missing = sorted(expected_names - actual_names)
            unexpected = sorted(actual_names - expected_names)
            raise ValueError(
                f"Expected exactly EC_001.json through EC_050.json; "
                f"missing={missing}, unexpected={unexpected}"
            )
        if not paths:
            raise ValueError("No input case files found")

        repository = OlistRepository(self.data_dir)
        coordinator = CoordinatorAgent()
        records: list[dict] = []
        for path in paths:
            case = read_case(path)
            result = coordinator.resolve(case, repository.facts_for(case.claimed_order_id))
            write_json(self.output_dir / path.name, result)
            records.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "case_resolved",
                "case_id": case.case_id,
                "claimed_order_id": case.claimed_order_id,
                "primary_issue": result["assessment"]["primary_issue"],
                "case_status": result["assessment"]["case_status"],
                "output_file": str(self.output_dir / path.name),
            })
        self._replace_trace(records)
        return len(records)

    def _replace_trace(self, records: list[dict]) -> None:
        """Replace, never append: the assignment requests only the latest run trace."""
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("w", encoding="utf-8", newline="\n") as file:
            for record in records:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")
