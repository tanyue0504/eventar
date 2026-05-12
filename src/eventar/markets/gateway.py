"""订单网关组件。

OrderGateway 负责接收订单命令并执行校验职责链：
- 监听 ``Order``（PRE 阶段），自动覆盖所有 ``Order`` 子类命令；
- 校验通过后发布 ``OrderAccepted``；
- 校验失败后发布 ``OrderRejected``。
"""
from __future__ import annotations

from collections.abc import Callable, Iterable

from eventar.kernel import Component, EventEngine, Phase
from eventar.markets.order import Order, OrderAccepted, OrderRejected

OrderValidator = Callable[[Order], str | None]


class OrderGateway(Component):
    """订单网关：基于校验职责链处理新订单命令。"""

    def __init__(
        self,
        engine: EventEngine,
        validators: Iterable[OrderValidator] | None = None,
    ) -> None:
        super().__init__(engine)
        self._validators: list[OrderValidator] = list(validators or [])

    def add_validator(self, validator: OrderValidator) -> None:
        """追加一个校验器到职责链末尾。"""
        self._validators.append(validator)

    def start(self) -> None:
        self.engine.register(Order, self.on_order, Phase.PRE)

    def stop(self) -> None:
        self.engine.unregister(Order, self.on_order, Phase.PRE)

    def on_order(self, order: Order) -> None:
        """处理订单命令并发布结果事件。"""
        for validator in self._validators:
            reason = validator(order)
            if reason:
                self.engine.push(OrderRejected(order_id=order.order_id, reason=reason))
                return
        self.engine.push(OrderAccepted(order_id=order.order_id))
