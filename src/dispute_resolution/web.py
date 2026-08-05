"""Local browser dashboard for inspecting dispute-resolution agent handoffs."""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
from collections import Counter
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .analysis import CaseAnalysisPipeline
from .case_io import read_case
from .coordinator import CoordinatorAgent
from .policy import PolicyAgent
from .repository import OlistRepository


CASE_ID_PATTERN = re.compile(r"^EC_\d{3}$")
STATIC_DIR = Path(__file__).with_name("static")


def _json_default(value: object):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class AgentDashboard:
    """Read-only façade around the real pipeline used by the batch runner."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.input_dir = project_root / "input"
        self.repository = OlistRepository(project_root / "data")
        self.pipeline = CaseAnalysisPipeline()
        self.policy = PolicyAgent()
        self.coordinator = CoordinatorAgent()

    def case_ids(self) -> list[str]:
        return [path.stem for path in sorted(self.input_dir.glob("EC_*.json"))]

    def inspect(self, case_id: str) -> dict:
        if not CASE_ID_PATTERN.fullmatch(case_id):
            raise ValueError("case_id must follow the EC_001 format")
        path = self.input_dir / f"{case_id}.json"
        if not path.is_file():
            raise FileNotFoundError(f"Case {case_id} was not found")
        case = read_case(path)
        facts = self.repository.facts_for(case.claimed_order_id)
        analysis = self.pipeline.analyse(facts)
        decision = self.policy.decide(facts, analysis)
        return {
            "case": asdict(case),
            "facts": {
                "order": asdict(facts.order) if facts.order else None,
                "items": [asdict(item) for item in facts.items],
                "payments": [asdict(payment) for payment in facts.payments],
                "totals": {
                    "item_total_brl": facts.item_total,
                    "freight_total_brl": facts.freight_total,
                    "payment_total_brl": facts.payment_total,
                },
            },
            "agent_handoffs": {
                "order_seller": asdict(analysis.order_seller),
                "payment": asdict(analysis.payment),
                "delivery": asdict(analysis.delivery),
            },
            "policy_decision": asdict(decision),
            "output": self.coordinator.resolve(case, facts),
        }

    def summary(self) -> dict:
        cases = []
        issues: Counter[str] = Counter()
        for case_id in self.case_ids():
            output = self.inspect(case_id)["output"]
            assessment = output["assessment"]
            issue = assessment["primary_issue"]
            issues[issue] += 1
            cases.append({
                "case_id": case_id,
                "primary_issue": issue,
                "case_status": assessment["case_status"],
                "recommended_refund_brl": output["financial_resolution"]["recommended_refund_brl"],
            })
        return {"total_cases": len(cases), "issues": dict(sorted(issues.items())), "cases": cases}


def make_handler(dashboard: AgentDashboard):
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            route = urlparse(self.path).path
            try:
                if route == "/api/cases":
                    self._send_json({"case_ids": dashboard.case_ids()})
                elif route == "/api/summary":
                    self._send_json(dashboard.summary())
                elif route.startswith("/api/cases/"):
                    self._send_json(dashboard.inspect(route.removeprefix("/api/cases/")))
                elif route in {"/", "/index.html", "/app.js", "/styles.css"}:
                    self._send_static("index.html" if route in {"/", "/index.html"} else route.lstrip("/"))
                else:
                    self._send_error(HTTPStatus.NOT_FOUND, "Route not found")
            except FileNotFoundError as error:
                self._send_error(HTTPStatus.NOT_FOUND, str(error))
            except ValueError as error:
                self._send_error(HTTPStatus.BAD_REQUEST, str(error))
            except Exception as error:
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(error))

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            return

        def _send_json(self, payload: dict) -> None:
            self._send_json_with_status(HTTPStatus.OK, payload, indent=2)

        def _send_static(self, filename: str) -> None:
            path = STATIC_DIR / filename
            if not path.is_file():
                self._send_error(HTTPStatus.NOT_FOUND, "Static file not found")
                return
            body = path.read_bytes()
            content_type, _ = mimetypes.guess_type(path.name)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{content_type or 'application/octet-stream'}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, status: HTTPStatus, message: str) -> None:
            self._send_json_with_status(status, {"error": message})

        def _send_json_with_status(self, status: HTTPStatus, payload: dict, indent: int | None = None) -> None:
            body = json.dumps(payload, ensure_ascii=False, default=_json_default, indent=indent).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return DashboardHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local dispute-resolution agent dashboard.")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    dashboard = AgentDashboard(args.project_root.resolve())
    server = ThreadingHTTPServer((args.host, args.port), make_handler(dashboard))
    print(f"Agent dashboard: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAgent dashboard stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
