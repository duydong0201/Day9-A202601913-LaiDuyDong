"""Runs the specialised agents and exposes a single validated case handoff."""

from __future__ import annotations

from dataclasses import dataclass

from .agents import DeliveryAgent, DeliveryHandoff, OrderSellerAgent, OrderSellerHandoff, PaymentAgent, PaymentHandoff
from .contracts import OrderFacts


@dataclass(frozen=True)
class AnalysisBundle:
    order_seller: OrderSellerHandoff
    payment: PaymentHandoff
    delivery: DeliveryHandoff


class CaseAnalysisPipeline:
    def __init__(self) -> None:
        self.order_seller_agent = OrderSellerAgent()
        self.payment_agent = PaymentAgent()
        self.delivery_agent = DeliveryAgent()

    def analyse(self, facts: OrderFacts) -> AnalysisBundle:
        return AnalysisBundle(
            order_seller=self.order_seller_agent.inspect(facts),
            payment=self.payment_agent.inspect(facts),
            delivery=self.delivery_agent.inspect(facts),
        )
