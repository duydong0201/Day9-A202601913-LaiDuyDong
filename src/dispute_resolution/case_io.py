"""Strict JSON input/output helpers for the dispute-resolution batch runner."""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import CaseInput


def read_case(path: Path) -> CaseInput:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    try:
        request = payload["customer_request"]
        case = CaseInput(
            case_id=payload["case_id"],
            opened_at=payload["opened_at"],
            language=request["language"],
            message=request["message"],
            claimed_order_id=request["claimed_order_id"],
            policy_version=payload["policy_version"],
        )
    except (KeyError, TypeError) as error:
        raise ValueError(f"Invalid input schema: {path.name}") from error
    if case.policy_version != "EC_POLICY_V1":
        raise ValueError(f"Unsupported policy version in {path.name}: {case.policy_version}")
    if path.stem != case.case_id:
        raise ValueError(f"Input filename and case_id differ: {path.name}")
    return case


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
