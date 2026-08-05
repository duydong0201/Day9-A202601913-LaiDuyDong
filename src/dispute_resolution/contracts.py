"""Shared immutable contracts passed between the specialised agents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal


IssueCode = Literal[
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
    "late_delivery_logistics",
    "valid_split_payment",
    "unsupported_late_claim",
]


@dataclass(frozen=True)
class CaseInput:
    case_id: str
    opened_at: str
    language: str
    message: str
    claimed_order_id: str
    policy_version: str


@dataclass(frozen=True)
class OrderRecord:
    order_id: str
    customer_id: str
    status: str
    purchase_at: datetime | None
    approved_at: datetime | None
    delivered_to_carrier_at: datetime | None
    delivered_to_customer_at: datetime | None
    estimated_delivery_at: datetime | None


@dataclass(frozen=True)
class OrderItemRecord:
    order_id: str
    item_id: int
    product_id: str
    seller_id: str
    shipping_limit_at: datetime | None
    price: Decimal
    freight_value: Decimal


@dataclass(frozen=True)
class PaymentRecord:
    order_id: str
    sequential: int
    payment_type: str
    installments: int
    value: Decimal


@dataclass(frozen=True)
class OrderFacts:
    """Verified data snapshot assembled before policy evaluation."""

    order: OrderRecord | None
    items: tuple[OrderItemRecord, ...]
    payments: tuple[PaymentRecord, ...]

    @property
    def item_total(self) -> Decimal:
        return sum((item.price for item in self.items), Decimal("0"))

    @property
    def freight_total(self) -> Decimal:
        return sum((item.freight_value for item in self.items), Decimal("0"))

    @property
    def payment_total(self) -> Decimal:
        return sum((payment.value for payment in self.payments), Decimal("0"))
