"""Specialised, deterministic data-analysis agents.

Each agent receives only the verified ``OrderFacts`` assembled from the CSV
repository and returns a typed handoff to the Coordinator/Policy stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .contracts import OrderFacts


@dataclass(frozen=True)
class OrderSellerHandoff:
    order_exists: bool
    order_status: str | None
    item_ids: tuple[str, ...]
    seller_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class PaymentHandoff:
    payment_ids: tuple[str, ...]
    payment_total: Decimal
    merchandise_and_freight_total: Decimal
    payment_matches_order_total: bool
    has_multiple_payments: bool
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class DeliveryHandoff:
    delivered_after_estimate: bool
    seller_ids_after_shipping_limit: tuple[str, ...]
    delivery_data_complete: bool
    evidence_ids: tuple[str, ...]


class OrderSellerAgent:
    """Extracts order, item and seller entities without making policy decisions."""

    def inspect(self, facts: OrderFacts) -> OrderSellerHandoff:
        if facts.order is None:
            return OrderSellerHandoff(False, None, (), (), ())

        item_ids = tuple(f"{item.order_id}:{item.item_id}" for item in facts.items)
        seller_ids = tuple(dict.fromkeys(item.seller_id for item in facts.items))
        evidence = [f"order:{facts.order.order_id}"]
        evidence.extend(f"item:{item.order_id}:{item.item_id}" for item in facts.items)
        evidence.extend(f"seller:{seller_id}" for seller_id in seller_ids)
        return OrderSellerHandoff(
            order_exists=True,
            order_status=facts.order.status,
            item_ids=item_ids,
            seller_ids=seller_ids,
            evidence_ids=tuple(evidence),
        )


class PaymentAgent:
    """Reconciles payment rows against the order merchandise and freight."""

    ALLOWED_DIFFERENCE = Decimal("0.10")

    def inspect(self, facts: OrderFacts) -> PaymentHandoff:
        payment_ids = tuple(
            f"{payment.order_id}:{payment.sequential}" for payment in facts.payments
        )
        expected_total = facts.item_total + facts.freight_total
        matches = abs(facts.payment_total - expected_total) <= self.ALLOWED_DIFFERENCE
        evidence = tuple(
            f"payment:{payment.order_id}:{payment.sequential}" for payment in facts.payments
        )
        return PaymentHandoff(
            payment_ids=payment_ids,
            payment_total=facts.payment_total,
            merchandise_and_freight_total=expected_total,
            payment_matches_order_total=matches,
            has_multiple_payments=len(facts.payments) >= 2,
            evidence_ids=evidence,
        )


class DeliveryAgent:
    """Checks delivery lateness and seller handoff deadlines from CSV timestamps."""

    def inspect(self, facts: OrderFacts) -> DeliveryHandoff:
        order = facts.order
        if order is None:
            return DeliveryHandoff(False, (), False, ())

        delivery_data_complete = (
            order.delivered_to_customer_at is not None
            and order.estimated_delivery_at is not None
            and order.delivered_to_carrier_at is not None
        )
        delivered_after_estimate = bool(
            order.delivered_to_customer_at
            and order.estimated_delivery_at
            and order.delivered_to_customer_at > order.estimated_delivery_at
        )
        late_sellers = tuple(dict.fromkeys(
            item.seller_id
            for item in facts.items
            if order.delivered_to_carrier_at is not None
            and item.shipping_limit_at is not None
            and order.delivered_to_carrier_at > item.shipping_limit_at
        ))
        evidence = [f"order:{order.order_id}"]
        evidence.extend(f"item:{item.order_id}:{item.item_id}" for item in facts.items)
        evidence.extend(f"seller:{seller_id}" for seller_id in late_sellers)
        return DeliveryHandoff(
            delivered_after_estimate=delivered_after_estimate,
            seller_ids_after_shipping_limit=late_sellers,
            delivery_data_complete=delivery_data_complete,
            evidence_ids=tuple(evidence),
        )
