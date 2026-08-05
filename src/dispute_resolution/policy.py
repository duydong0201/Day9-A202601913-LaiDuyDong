"""Deterministic implementation of the EC_POLICY_V1 precedence rules."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .analysis import AnalysisBundle
from .contracts import OrderFacts


@dataclass(frozen=True)
class ResponsibleParty:
    party_type: str
    party_id: str


@dataclass(frozen=True)
class PolicyDecision:
    primary_issue: str
    root_cause_code: str
    responsible_parties: tuple[ResponsibleParty, ...]
    recommended_refund: Decimal
    actions: tuple[str, ...]
    case_status: str
    confidence: float


class PolicyAgent:
    """Applies only documented rules; it never fills gaps with invented events."""

    def decide(self, facts: OrderFacts, analysis: AnalysisBundle) -> PolicyDecision:
        order = facts.order
        if order is None:
            raise ValueError("Cannot apply EC_POLICY_V1: claimed order does not exist")

        # Precedence follows the order specified in README.md.
        if order.status == "canceled" and facts.payment_total > 0:
            return self._decision(
                "canceled_order_paid", "ORDER_CANCELED_AFTER_PAYMENT",
                (ResponsibleParty("platform", "OLIST_PLATFORM"),), facts.payment_total,
                "issue_full_refund", 0.99,
            )
        if order.status == "unavailable" and facts.payment_total > 0:
            return self._decision(
                "unavailable_order_paid", "ORDER_UNAVAILABLE_AFTER_PAYMENT",
                (ResponsibleParty("platform", "OLIST_PLATFORM"),), facts.payment_total,
                "issue_full_refund", 0.99,
            )
        if analysis.delivery.delivered_after_estimate:
            late_sellers = analysis.delivery.seller_ids_after_shipping_limit
            if late_sellers:
                return self._decision(
                    "late_delivery_seller", "SELLER_HANDOFF_AFTER_LIMIT",
                    tuple(ResponsibleParty("seller", seller_id) for seller_id in late_sellers),
                    facts.freight_total, "refund_freight", 0.97,
                )
            return self._decision(
                "late_delivery_logistics", "CARRIER_DELIVERED_AFTER_ESTIMATE",
                (ResponsibleParty("logistics_provider", "LOGISTICS_PROVIDER"),),
                facts.freight_total, "refund_freight", 0.97,
            )
        if analysis.payment.has_multiple_payments and analysis.payment.payment_matches_order_total:
            return self._decision(
                "valid_split_payment", "MULTIPLE_PAYMENTS_RECONCILED", (), Decimal("0"),
                "explain_valid_split_payment", 0.98,
            )
        if not analysis.delivery.delivered_after_estimate and analysis.payment.payment_matches_order_total:
            return self._decision(
                "unsupported_late_claim", "DELIVERY_WITHIN_ESTIMATE", (), Decimal("0"),
                "reject_late_refund", 0.96,
            )
        raise ValueError("Facts do not satisfy a documented EC_POLICY_V1 rule")

    @staticmethod
    def _decision(
        issue: str,
        root_cause: str,
        parties: tuple[ResponsibleParty, ...],
        refund: Decimal,
        action: str,
        confidence: float,
    ) -> PolicyDecision:
        return PolicyDecision(
            primary_issue=issue,
            root_cause_code=root_cause,
            responsible_parties=parties,
            recommended_refund=refund,
            actions=(action,),
            case_status="action_required" if refund > 0 else "no_action",
            confidence=confidence,
        )
