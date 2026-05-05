"""事件引擎定义。

支持三层监听：
1. 全局优先监听（先执行）
2. 按事件类型路由监听（中间执行）
3. 全局劣后监听（最后执行）

事件通过 ``push`` 进入 FIFO ``deque`` 队列，``run`` 循环消费直到队列为空。
"""

from collections import deque
from collections.abc import Callable

from eventar.core.event import Event

EventListener = Callable[[Event], None]


class EventEngine:
    """基于 deque 的单线程 FIFO 事件引擎。"""

    def __init__(self) -> None:
        self._event_queue: deque[Event] = deque()
        self._global_pre_listeners: list[EventListener] = []
        self._global_post_listeners: list[EventListener] = []
        self._typed_listeners: dict[type[Event], list[EventListener]] = {}

        self._is_dispatching = False

    def register_global_pre(self, listener: EventListener) -> None:
        """注册全局优先监听器。"""
        self._global_pre_listeners.append(listener)

    def unregister_global_pre(self, listener: EventListener) -> None:
        """取消全局优先监听器。"""
        self._global_pre_listeners.remove(listener)

    def register_global_post(self, listener: EventListener) -> None:
        """注册全局劣后监听器。"""
        self._global_post_listeners.append(listener)

    def unregister_global_post(self, listener: EventListener) -> None:
        """取消全局劣后监听器。"""
        self._global_post_listeners.remove(listener)

    def register_for(self, event_type: type[Event], listener: EventListener) -> None:
        """为某个事件类型注册监听器。"""
        listeners = self._typed_listeners.setdefault(event_type, [])
        listeners.append(listener)

    def unregister_for(self, event_type: type[Event], listener: EventListener) -> None:
        """取消某个事件类型的监听器。"""
        listeners = self._typed_listeners.get(event_type, [])
        listeners.remove(listener)

    def push(self, event: Event) -> None:
        """将事件压入 FIFO 队列尾部。"""
        if self._is_dispatching:
            # 派发过程中收到新事件时，只入队，交由外层 drain 统一处理。
            self._event_queue.append(event)
            return

        self._is_dispatching = True
        # 短路径：首个事件立即派发，减少一次不必要的入队/出队。
        self._dispatch(event)
        while self._event_queue:
            queued_event = self._event_queue.popleft()
            self._dispatch(queued_event)
        self._is_dispatching = False

    def _dispatch(self, event: Event) -> None:
        event_type = type(event)

        for listener in self._global_pre_listeners:
            listener(event)

        for listener in self._typed_listeners.get(event_type, []):
            listener(event)

        for listener in self._global_post_listeners:
            listener(event)
