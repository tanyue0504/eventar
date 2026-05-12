"""市场订单通信标准抽象。

该模块只定义跨市场共享的订单通信事件与命令，不包含任何市场细节：
- 具体订单参数由各市场在 ``Order`` 子类中扩展。
- 风控/校验职责链、撮合规则、订单簿维护逻辑由上层组件实现。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count

from eventar.kernel import Event

_ORDER_ID_COUNTER = count(1)


def _next_order_id() -> int:
	return next(_ORDER_ID_COUNTER)


# 说明：Order 表示策略发给网关的“新订单命令”。
# 这是一个“意图”，而不是处理结果，因此需要独立于订单生命周期事件。
# 具体市场通过继承 Order 扩展参数（如方向、价格、数量）；order_id 在这里统一自动分配。
@dataclass(frozen=True, slots=True)
class Order(Event):
	"""策略发出的新订单抽象基类。

	具体市场应继承该类并补充订单参数（如方向、数量、价格、品种等）。
	``order_id`` 由框架全局自动分配，用于唯一标识订单。
	"""

	order_id: int = field(init=False, default_factory=_next_order_id)


@dataclass(frozen=True, slots=True)
class CancelOrder(Event):
	"""策略发出的撤单请求。"""

	order_id: int


# 说明：OrderEvent 表示订单处理过程中“已经发生的事实事件”。
# 例如接收、拒绝、成交、撤单接收/拒绝都属于该层，它们只引用既有 order_id，
# 不应再创建新订单 id。这样可以清晰分离“命令输入”和“结果输出”。
@dataclass(frozen=True, slots=True)
class OrderEvent(Event):
	"""与订单生命周期相关的事件基类。"""

	order_id: int


@dataclass(frozen=True, slots=True)
class OrderAccepted(OrderEvent):
	"""网关校验通过，订单被接收。"""


@dataclass(frozen=True, slots=True)
class OrderRejected(OrderEvent):
	"""网关校验失败，订单被拒绝。"""

	reason: str = ""


@dataclass(frozen=True, slots=True)
class OrderFilled(OrderEvent):
	"""撮合器发出的成交事件。"""


@dataclass(frozen=True, slots=True)
class CancelAccepted(OrderEvent):
	"""撤单请求被接收。"""


@dataclass(frozen=True, slots=True)
class CancelRejected(OrderEvent):
	"""撤单请求被拒绝。"""

	reason: str = ""

__all__ = [
	"Order",
	"OrderEvent",
	"OrderAccepted",
	"CancelOrder",
	"CancelAccepted",
	"CancelRejected",
	"OrderFilled",
	"OrderRejected",
]
