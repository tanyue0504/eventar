"""事件引擎定义。

路由模型
--------
注册时指定监听的事件类型 ``event_type``；派发时，引擎遍历 ``type(event).__mro__``，
将所有注册在 MRO 链上任意类型的监听器合并后按注册顺序触发。
这意味着注册在父类（如 ``Order``）的监听器，能自动接收其所有子类实例。

阶段（Phase）
-------------
每个监听器注册时携带一个 ``Phase``（默认 ``Phase.MAIN``），引擎按
``PRE → MAIN → POST`` 顺序触发，同阶段内按注册顺序触发。
无需全局监听器接口——监听 ``Event`` 根类即可实现"全局"效果，
并通过 Phase 控制执行时机。

路由缓存
--------
内部维护 ``_route_cache``，按 Phase 和事件类型缓存 MRO 解析后的监听器列表。
每次 register / unregister 操作后清空对应 Phase 的全部缓存；派发时懒惰填充。

FIFO 队列
---------
事件通过 ``push`` 进入 FIFO ``deque`` 队列，在当前派发轮结束前 drain 到空。
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from enum import Enum, auto

from eventar.kernel.event import Event

EventListener = Callable[[Event], None]


class Phase(Enum):
    """事件监听器的执行阶段。

    同阶段内，监听器按注册顺序触发。
    跨阶段按 PRE → MAIN → POST 顺序触发，不可调整。
    """

    PRE = auto()
    MAIN = auto()
    POST = auto()


class EventEngine:
    """基于 deque 的单线程 FIFO 事件引擎，支持 MRO 继承路由与三阶段派发。"""

    def __init__(self) -> None:
        self._event_queue: deque[Event] = deque()
        # 注册表：{ Phase: { event_type: [listeners] } }
        self._listeners: dict[Phase, dict[type, list[EventListener]]] = {
            Phase.PRE: {},
            Phase.MAIN: {},
            Phase.POST: {},
        }
        # 路由缓存：{ Phase: { concrete_event_type: [resolved_listeners] } }
        # 派发时懒惰填充，register/unregister 时按 Phase 清空。
        self._route_cache: dict[Phase, dict[type, list[EventListener]]] = {
            Phase.PRE: {},
            Phase.MAIN: {},
            Phase.POST: {},
        }
        self._is_dispatching = False

    def register(
        self,
        event_type: type[Event],
        listener: EventListener,
        phase: Phase = Phase.MAIN,
    ) -> None:
        """注册监听器。

        Parameters
        ----------
        event_type:
            要监听的事件类型。派发时，该类型及其所有子类的事件都会触发此监听器。
        listener:
            监听器回调，接收单个事件实例。
        phase:
            执行阶段，默认 ``Phase.MAIN``。
        """
        self._listeners[phase].setdefault(event_type, []).append(listener)
        self._route_cache[phase].clear()

    def unregister(
        self,
        event_type: type[Event],
        listener: EventListener,
        phase: Phase = Phase.MAIN,
    ) -> None:
        """取消监听器。

        Raises
        ------
        ValueError
            如果该监听器未注册，行为与 ``list.remove`` 一致，抛出 ``ValueError``。
        """
        self._listeners[phase].get(event_type, []).remove(listener)
        self._route_cache[phase].clear()

    def push(self, event: Event) -> None:
        """将事件推入引擎。

        若当前已在派发轮次中（监听器内部再次调用 push），则入队等待；
        否则立即派发，并 drain 队列直到为空。
        """
        if self._is_dispatching:
            self._event_queue.append(event)
            return

        self._is_dispatching = True
        self._dispatch(event)
        while self._event_queue:
            self._dispatch(self._event_queue.popleft())
        self._is_dispatching = False

    def _dispatch(self, event: Event) -> None:
        """按 PRE → MAIN → POST 顺序触发所有匹配监听器。"""
        event_type = type(event)
        for phase in (Phase.PRE, Phase.MAIN, Phase.POST):
            resolved = self._route_cache[phase].get(event_type)
            if resolved is None:
                resolved = []
                for cls in event_type.__mro__:
                    if cls in self._listeners[phase]:
                        resolved.extend(self._listeners[phase][cls])
                self._route_cache[phase][event_type] = resolved
            for listener in resolved:
                listener(event)
