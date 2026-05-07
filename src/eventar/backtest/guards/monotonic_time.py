from eventar.kernel.component import Component
from eventar.kernel.engine import EventEngine
from eventar.kernel.event import Event
from eventar.data import DataEvent

class MonotonicTimeGuard(Component):
    """时间守卫组件。
    
    监听 TimerEvent，根据事件时间戳控制回测引擎的运行状态。
    """
    def __init__(self, engine: EventEngine) -> None:
        super().__init__(engine)
        self.cache_event: DataEvent | None = None

    def start(self) -> None:
        self.engine.register_global_pre(self.on_event)

    def stop(self) -> None:
        self.engine.unregister_global_pre(self.on_event)

    def on_event(self, event: Event) -> None:
        if not isinstance(event, DataEvent):
            return
        if self.cache_event is None:
            self.cache_event = event
            return
        if event.timestamp < self.cache_event.timestamp:
            raise RuntimeError(
                f"时光回溯：{event}早于{self.cache_event}，引擎将停止运行。"
            )
        self.cache_event = event