"""Read-only access to the Olist CSV source of truth.

The repository deliberately keeps the CSV files authoritative.  It only creates
in-memory indexes needed for a case, avoiding fabricated operational events.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .contracts import OrderFacts, OrderItemRecord, OrderRecord, PaymentRecord


def _date(value: str) -> datetime | None:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S") if value else None


class OlistRepository:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._orders = self._load_orders()
        self._items = self._load_items()
        self._payments = self._load_payments()

    def facts_for(self, order_id: str) -> OrderFacts:
        return OrderFacts(
            order=self._orders.get(order_id),
            items=tuple(self._items.get(order_id, ())),
            payments=tuple(self._payments.get(order_id, ())),
        )

    def _rows(self, filename: str):
        with (self.data_dir / filename).open("r", encoding="utf-8", newline="") as file:
            yield from csv.DictReader(file)

    def _load_orders(self) -> dict[str, OrderRecord]:
        return {
            row["order_id"]: OrderRecord(
                order_id=row["order_id"], customer_id=row["customer_id"], status=row["order_status"],
                purchase_at=_date(row["order_purchase_timestamp"]), approved_at=_date(row["order_approved_at"]),
                delivered_to_carrier_at=_date(row["order_delivered_carrier_date"]),
                delivered_to_customer_at=_date(row["order_delivered_customer_date"]),
                estimated_delivery_at=_date(row["order_estimated_delivery_date"]),
            )
            for row in self._rows("olist_orders_dataset.csv")
        }

    def _load_items(self) -> dict[str, list[OrderItemRecord]]:
        result: dict[str, list[OrderItemRecord]] = defaultdict(list)
        for row in self._rows("olist_order_items_dataset.csv"):
            result[row["order_id"]].append(OrderItemRecord(
                order_id=row["order_id"], item_id=int(row["order_item_id"]), product_id=row["product_id"],
                seller_id=row["seller_id"], shipping_limit_at=_date(row["shipping_limit_date"]),
                price=Decimal(row["price"]), freight_value=Decimal(row["freight_value"]),
            ))
        return result

    def _load_payments(self) -> dict[str, list[PaymentRecord]]:
        result: dict[str, list[PaymentRecord]] = defaultdict(list)
        for row in self._rows("olist_order_payments_dataset.csv"):
            result[row["order_id"]].append(PaymentRecord(
                order_id=row["order_id"], sequential=int(row["payment_sequential"]),
                payment_type=row["payment_type"], installments=int(row["payment_installments"]),
                value=Decimal(row["payment_value"]),
            ))
        return result
