"""订单簿组件。

OrderBook 负责维护活动订单状态并处理撤单：
- 监听 ``OrderAccepted``：将订单标记为活动；
- 监听 ``CancelOrder``：活动订单撤单成功，否则拒绝；
- 监听 ``OrderFilled``：成交后从活动集合移除。
"""
from __future__ import annotations

from eventar.kernel import Component, EventEngine, Phase
from eventar.markets.order import (
    CancelAccepted,
    CancelOrder,
    CancelRejected,
    OrderAccepted,
    OrderFilled,
)


class OrderBook(Component):
    """最小活动订单簿。"""

    def __init__(self, engine: EventEngine) -> None:
        super().__init__(engine)
        self._active_order_ids: set[int] = set()

    @property
    def active_order_ids(self) -> frozenset[int]:
        return frozenset(self._active_order_ids)

    def start(self) -> None:
        self.engine.register(OrderAccepted, self.on_order_accepted, Phase.MAIN)
        self.engine.register(CancelOrder, self.on_cancel_order, Phase.MAIN)
        self.engine.register(OrderFilled, self.on_order_filled, Phase.MAIN)

    def stop(self) -> None:
        self.engine.unregister(OrderAccepted, self.on_order_accepted, Phase.MAIN)
        self.engine.unregister(CancelOrder, self.on_cancel_order, Phase.MAIN)
        self.engine.unregister(OrderFilled, self.on_order_filled, Phase.MAIN)

    def on_order_accepted(self, event: OrderAccepted) -> None:
        self._active_order_ids.add(event.order_id)

    def on_cancel_order(self, event: CancelOrder) -> None:
        if event.order_id in self._active_order_ids:
            self._active_order_ids.remove(event.order_id)
            self.engine.push(CancelAccepted(order_id=event.order_id))
            return
        self.engine.push(CancelRejected(order_id=event.order_id, reason="order not in active set"))

    def on_order_filled(self, event: OrderFilled) -> None:
        self._active_order_ids.remove(event.order_id)
