"""Minimal smoke-test entry point; orchestration is added in the next phase."""

from __future__ import annotations

import argparse
from pathlib import Path

from .analysis import CaseAnalysisPipeline
from .repository import OlistRepository
from .runner import BatchRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect verified Olist data for one order.")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Inspect one order's verified data")
    inspect.add_argument("order_id")
    inspect.add_argument("--data-dir", type=Path, default=Path("data"))
    run = commands.add_parser("run", help="Resolve submitted cases in batch")
    run.add_argument("--data-dir", type=Path, default=Path("data"))
    run.add_argument("--input-dir", type=Path, default=Path("input"))
    run.add_argument("--output-dir", type=Path, default=Path("output"))
    run.add_argument("--trace-path", type=Path, default=Path("trace.jsonl"))
    run.add_argument("--allow-partial", action="store_true", help="Allow fewer than 50 cases for local development")
    args = parser.parse_args()
    if args.command == "run":
        completed = BatchRunner(
            data_dir=args.data_dir,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            trace_path=args.trace_path,
        ).run(require_50_cases=not args.allow_partial)
        print(f"resolved_cases={completed}")
        return

    facts = OlistRepository(args.data_dir).facts_for(args.order_id)
    analysis = CaseAnalysisPipeline().analyse(facts)
    print(
        f"order_found={analysis.order_seller.order_exists} "
        f"items={len(analysis.order_seller.item_ids)} "
        f"payments={len(analysis.payment.payment_ids)} "
        f"payment_matches={analysis.payment.payment_matches_order_total} "
        f"late_delivery={analysis.delivery.delivered_after_estimate}"
    )


if __name__ == "__main__":
    main()
