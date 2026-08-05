"""Output verifier that rejects unsupported IDs and malformed policy results."""

from __future__ import annotations

from decimal import Decimal

from .contracts import CaseInput, OrderFacts


class OutputVerifier:
    REQUIRED_TOP_LEVEL = {
        "case_id", "assessment", "affected_entities", "root_cause_analysis",
        "evidence_ids", "financial_resolution", "resolution_actions",
    }

    def verify(self, result: dict, case: CaseInput, facts: OrderFacts) -> None:
        if set(result) != self.REQUIRED_TOP_LEVEL:
            raise ValueError("Output does not match the required top-level schema")
        if result["case_id"] != case.case_id:
            raise ValueError("Output case_id does not match input")
        confidence = result["assessment"].get("confidence")
        if not isinstance(confidence, (float, int)) or not 0 <= confidence <= 1:
            raise ValueError("confidence must be in [0, 1]")
        self._verify_limits(result)
        self._verify_entities(result, facts)
        self._verify_financials(result, facts)
        self._verify_evidence(result, facts)
        self._verify_status(result)

    @staticmethod
    def _verify_limits(result: dict) -> None:
        entities = result["affected_entities"]
        if any(len(entities[name]) > 5 for name in ("order_ids", "item_ids", "seller_ids", "payment_ids")):
            raise ValueError("Affected entity limit exceeded")
        causes = result["root_cause_analysis"]
        if len(result["evidence_ids"]) > 10 or len(causes["ranked_causes"]) > 3:
            raise ValueError("Evidence or root-cause limit exceeded")
        if len(causes["responsible_parties"]) > 3 or len(result["resolution_actions"]) > 5:
            raise ValueError("Responsible-party or action limit exceeded")

    @staticmethod
    def _verify_entities(result: dict, facts: OrderFacts) -> None:
        entities = result["affected_entities"]
        valid_orders = {facts.order.order_id} if facts.order else set()
        valid_items = {f"{item.order_id}:{item.item_id}" for item in facts.items}
        valid_sellers = {item.seller_id for item in facts.items}
        valid_payments = {f"{payment.order_id}:{payment.sequential}" for payment in facts.payments}
        for values, valid, label in (
            (entities["order_ids"], valid_orders, "order"),
            (entities["item_ids"], valid_items, "item"),
            (entities["seller_ids"], valid_sellers, "seller"),
            (entities["payment_ids"], valid_payments, "payment"),
        ):
            if any(value not in valid for value in values):
                raise ValueError(f"Output contains an invalid {label} entity ID")

    @staticmethod
    def _verify_financials(result: dict, facts: OrderFacts) -> None:
        financial = result["financial_resolution"]
        expected = {
            "item_total_brl": facts.item_total,
            "freight_total_brl": facts.freight_total,
            "payment_total_brl": facts.payment_total,
        }
        if financial.get("currency") != "BRL":
            raise ValueError("Currency must be BRL")
        for key, value in expected.items():
            if Decimal(str(financial[key])).quantize(Decimal("0.01")) != value.quantize(Decimal("0.01")):
                raise ValueError(f"Incorrect {key}")

    @staticmethod
    def _verify_evidence(result: dict, facts: OrderFacts) -> None:
        valid = set()
        if facts.order:
            valid.add(f"order:{facts.order.order_id}")
        valid.update(f"item:{item.order_id}:{item.item_id}" for item in facts.items)
        valid.update(f"payment:{payment.order_id}:{payment.sequential}" for payment in facts.payments)
        valid.update(f"seller:{item.seller_id}" for item in facts.items)
        root_causes = result["root_cause_analysis"]["ranked_causes"]
        valid.update(f"policy:{cause['cause_code']}" for cause in root_causes)
        if any(evidence_id not in valid for evidence_id in result["evidence_ids"]):
            raise ValueError("Output contains invalid or unsupported evidence ID")

    @staticmethod
    def _verify_status(result: dict) -> None:
        refund = Decimal(str(result["financial_resolution"]["recommended_refund_brl"]))
        expected_status = "action_required" if refund > 0 else "no_action"
        if result["assessment"].get("case_status") != expected_status:
            raise ValueError("case_status is inconsistent with recommended_refund_brl")
