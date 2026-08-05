"""Coordinator that combines agent handoffs into the required output schema."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .analysis import CaseAnalysisPipeline
from .contracts import CaseInput, OrderFacts
from .policy import PolicyAgent
from .verifier import OutputVerifier


def _brl(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class CoordinatorAgent:
    def __init__(self) -> None:
        self.analysis_pipeline = CaseAnalysisPipeline()
        self.policy_agent = PolicyAgent()
        self.verifier = OutputVerifier()

    def resolve(self, case: CaseInput, facts: OrderFacts) -> dict:
        analysis = self.analysis_pipeline.analyse(facts)
        decision = self.policy_agent.decide(facts, analysis)
        order_id = facts.order.order_id if facts.order else case.claimed_order_id
        order_ids = [order_id] if facts.order else []
        evidence = self._evidence(analysis, decision.root_cause_code)
        result = {
            "case_id": case.case_id,
            "assessment": {
                "primary_issue": decision.primary_issue,
                "case_status": decision.case_status,
                "confidence": decision.confidence,
            },
            "affected_entities": {
                "order_ids": order_ids[:5],
                "item_ids": list(analysis.order_seller.item_ids[:5]),
                "seller_ids": list(analysis.order_seller.seller_ids[:5]),
                "payment_ids": list(analysis.payment.payment_ids[:5]),
            },
            "root_cause_analysis": {
                "ranked_causes": [{"cause_code": decision.root_cause_code, "rank": 1}],
                "responsible_parties": [
                    {"party_type": party.party_type, "party_id": party.party_id}
                    for party in decision.responsible_parties[:3]
                ],
            },
            "evidence_ids": evidence,
            "financial_resolution": {
                "currency": "BRL",
                "item_total_brl": _brl(facts.item_total),
                "freight_total_brl": _brl(facts.freight_total),
                "payment_total_brl": _brl(facts.payment_total),
                "recommended_refund_brl": _brl(decision.recommended_refund),
            },
            "resolution_actions": list(decision.actions[:5]),
        }
        self.verifier.verify(result, case, facts)
        return result

    @staticmethod
    def _evidence(analysis, root_cause_code: str) -> list[str]:
        # Preserve useful order while respecting the submission cap of 10 evidence IDs.
        candidates = (
            analysis.order_seller.evidence_ids
            + analysis.payment.evidence_ids
            + analysis.delivery.evidence_ids
            + (f"policy:{root_cause_code}",)
        )
        return list(dict.fromkeys(candidates))[:10]
