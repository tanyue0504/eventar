"""针对 src/eventar/markets/order.py 的单元测试。"""
from __future__ import annotations

import dataclasses
import sys

import pytest

from eventar.kernel import Event
from eventar.markets.order import (
    CancelAccepted,
    CancelOrder,
    CancelRejected,
    Order,
    OrderAccepted,
    OrderEvent,
    OrderFilled,
    OrderRejected,
)


@dataclasses.dataclass(frozen=True, slots=True)
class LimitOrder(Order):
    symbol: str
    qty: int


def test_order_is_event():
    order = LimitOrder(symbol="000001.SZ", qty=100)
    assert isinstance(order, Event)


def test_order_id_auto_increment():
    first = LimitOrder(symbol="A", qty=1)
    second = LimitOrder(symbol="A", qty=1)
    assert second.order_id == first.order_id + 1


def test_cancel_order_is_command_not_order_event():
    order = LimitOrder(symbol="A", qty=1)
    cancel = CancelOrder(order_id=order.order_id)
    assert isinstance(cancel, Event)
    assert not isinstance(cancel, OrderEvent)



def test_order_events_reference_existing_order_id():
    order = LimitOrder(symbol="A", qty=1)
    order_id = order.order_id

    accepted = OrderAccepted(order_id=order_id)
    rejected = OrderRejected(order_id=order_id, reason="risk")
    filled = OrderFilled(order_id=order_id)
    cancel_accepted = CancelAccepted(order_id=order_id)
    cancel_rejected = CancelRejected(order_id=order_id, reason="not_active")

    assert accepted.order_id == order_id
    assert rejected.order_id == order_id
    assert rejected.reason == "risk"
    assert filled.order_id == order_id
    assert cancel_accepted.order_id == order_id
    assert cancel_rejected.order_id == order_id
    assert cancel_rejected.reason == "not_active"


def test_cancel_order_does_not_consume_new_order_id():
    first = LimitOrder(symbol="A", qty=1)
    CancelOrder(order_id=first.order_id)
    second = LimitOrder(symbol="A", qty=1)
    assert second.order_id == first.order_id + 1


def main():
    """Run all tests via pytest."""
    sys.exit(pytest.main([__file__, "-v"]))


if __name__ == "__main__":
    main()
