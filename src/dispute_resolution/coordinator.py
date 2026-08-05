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
        evidence = self._evidence(facts, decision)
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
    def _evidence(facts: OrderFacts, decision) -> list[str]:
        """Return only the records that establish the selected policy branch.

        Evidence is deliberately ordered as ``order -> item -> payment ->
        seller -> policy``.  This keeps the handoff auditable and avoids
        diluting a case with otherwise valid but irrelevant entity IDs.
        ``policy:*`` is always retained, even for unusually large orders.
        """
        order_id = facts.order.order_id if facts.order else None
        order_evidence = [f"order:{order_id}"] if order_id else []
        all_item_evidence = [f"item:{item.order_id}:{item.item_id}" for item in facts.items]
        payment_evidence = [
            f"payment:{payment.order_id}:{payment.sequential}"
            for payment in facts.payments
        ]
        policy_evidence = [f"policy:{decision.root_cause_code}"]

        if decision.primary_issue in {"canceled_order_paid", "unavailable_order_paid"}:
            # Status plus paid amount establish the platform refund rule.
            candidates = order_evidence + payment_evidence
        elif decision.primary_issue == "late_delivery_seller":
            # Include only items whose shipping deadline was breached, then
            # the seller(s) held responsible by the policy.
            responsible_sellers = {
                party.party_id
                for party in decision.responsible_parties
                if party.party_type == "seller"
            }
            late_item_evidence = [
                f"item:{item.order_id}:{item.item_id}"
                for item in facts.items
                if (
                    item.seller_id in responsible_sellers
                    and facts.order is not None
                    and facts.order.delivered_to_carrier_at is not None
                    and item.shipping_limit_at is not None
                    and facts.order.delivered_to_carrier_at > item.shipping_limit_at
                )
            ]
            seller_evidence = [f"seller:{seller_id}" for seller_id in sorted(responsible_sellers)]
            candidates = order_evidence + late_item_evidence + payment_evidence + seller_evidence
        elif decision.primary_issue in {
            "late_delivery_logistics",
            "valid_split_payment",
            "unsupported_late_claim",
        }:
            # Delivery and payment reconciliation rely on the order/item and
            # payment records; a seller is not a causal party in these rules.
            candidates = order_evidence + all_item_evidence + payment_evidence
        else:  # Defensive fallback for future policy versions.
            candidates = order_evidence + all_item_evidence + payment_evidence

        # Deduplicate without disturbing canonical order.  Reserve one slot
        # for the policy evidence rather than accidentally truncating it.
        supporting = list(dict.fromkeys(candidates))[:9]
        return supporting + policy_evidence
