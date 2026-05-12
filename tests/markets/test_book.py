"""OrderBook 测试。"""
from __future__ import annotations

import dataclasses

from eventar.kernel import Component, EventEngine
from eventar.markets.book import OrderBook
from eventar.markets.gateway import OrderGateway
from eventar.markets.order import (
    CancelAccepted,
    CancelOrder,
    CancelRejected,
    Order,
    OrderAccepted,
    OrderFilled,
    OrderRejected,
)


@dataclasses.dataclass(frozen=True, slots=True)
class LimitOrder(Order):
    symbol: str
    qty: int


def test_book_is_component() -> None:
    book = OrderBook(EventEngine())
    assert isinstance(book, Component)


def test_order_accepted_adds_active_order() -> None:
    engine = EventEngine()
    book = OrderBook(engine)
    book.start()

    engine.push(OrderAccepted(order_id=101))

    assert 101 in book.active_order_ids


def test_cancel_active_order_emits_cancel_accepted() -> None:
    engine = EventEngine()
    book = OrderBook(engine)
    book.start()

    seen: list[int] = []
    engine.register(CancelAccepted, lambda e: seen.append(e.order_id))

    engine.push(OrderAccepted(order_id=11))
    engine.push(CancelOrder(order_id=11))

    assert seen == [11]
    assert 11 not in book.active_order_ids


def test_cancel_inactive_order_emits_cancel_rejected() -> None:
    engine = EventEngine()
    book = OrderBook(engine)
    book.start()

    seen: list[str] = []
    engine.register(CancelRejected, lambda e: seen.append(e.reason))

    engine.push(CancelOrder(order_id=999))

    assert seen == ["order not in active set"]


def test_order_filled_removes_active_order() -> None:
    engine = EventEngine()
    book = OrderBook(engine)
    book.start()

    engine.push(OrderAccepted(order_id=55))
    engine.push(OrderFilled(order_id=55))

    assert 55 not in book.active_order_ids


def test_gateway_and_book_integration_uses_mro_order_routing() -> None:
    def positive_qty(order: Order) -> str | None:
        qty = getattr(order, "qty", 1)
        if qty <= 0:
            return "qty<=0"
        return None

    engine = EventEngine()
    gateway = OrderGateway(engine, validators=[positive_qty])
    book = OrderBook(engine)
    gateway.start()
    book.start()

    accepted: list[int] = []
    rejected: list[str] = []
    cancel_accepted: list[int] = []

    engine.register(OrderAccepted, lambda e: accepted.append(e.order_id))
    engine.register(OrderRejected, lambda e: rejected.append(e.reason))
    engine.register(CancelAccepted, lambda e: cancel_accepted.append(e.order_id))

    good = LimitOrder(symbol="000001.SZ", qty=10)
    bad = LimitOrder(symbol="000001.SZ", qty=0)

    engine.push(good)
    engine.push(bad)
    engine.push(CancelOrder(order_id=good.order_id))

    assert accepted == [good.order_id]
    assert rejected == ["qty<=0"]
    assert cancel_accepted == [good.order_id]
