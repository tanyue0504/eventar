"""OrderGateway 测试。"""
from __future__ import annotations

import dataclasses

from eventar.kernel import Component, EventEngine
from eventar.markets.gateway import OrderGateway
from eventar.markets.order import Order, OrderAccepted, OrderRejected


@dataclasses.dataclass(frozen=True, slots=True)
class LimitOrder(Order):
    symbol: str
    qty: int


def test_gateway_is_component() -> None:
    gateway = OrderGateway(EventEngine())
    assert isinstance(gateway, Component)


def test_subclass_order_is_routed_and_accepted() -> None:
    engine = EventEngine()
    gateway = OrderGateway(engine)
    gateway.start()

    seen: list[int] = []
    engine.register(OrderAccepted, lambda e: seen.append(e.order_id))

    order = LimitOrder(symbol="000001.SZ", qty=100)
    engine.push(order)

    assert seen == [order.order_id]


def test_validator_chain_rejects_order() -> None:
    def positive_qty(order: Order) -> str | None:
        qty = getattr(order, "qty", 1)
        if qty <= 0:
            return "qty<=0"
        return None

    engine = EventEngine()
    gateway = OrderGateway(engine, validators=[positive_qty])
    gateway.start()

    reasons: list[str] = []
    engine.register(OrderRejected, lambda e: reasons.append(e.reason))

    engine.push(LimitOrder(symbol="000001.SZ", qty=0))

    assert reasons == ["qty<=0"]


def test_stop_unsubscribes_listener() -> None:
    engine = EventEngine()
    gateway = OrderGateway(engine)
    gateway.start()
    gateway.stop()

    seen: list[int] = []
    engine.register(OrderAccepted, lambda e: seen.append(e.order_id))

    engine.push(LimitOrder(symbol="000001.SZ", qty=1))

    assert seen == []
