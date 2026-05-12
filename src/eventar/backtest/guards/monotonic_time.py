from eventar.kernel.component import Component
from eventar.kernel.engine import EventEngine, Phase
from eventar.data import DataEvent

class MonotonicTimeGuard(Component):
    """时间守卫组件。
    
    监听 DataEvent，根据事件时间戳控制回测引擎的运行状态。
    """
    def __init__(self, engine: EventEngine) -> None:
        super().__init__(engine)
        self.cache_event: DataEvent | None = None

    def start(self) -> None:
        self.engine.register(DataEvent, self.on_dataevent, Phase.PRE)

    def stop(self) -> None:
        self.engine.unregister(DataEvent, self.on_dataevent, Phase.PRE)

    def on_dataevent(self, event: DataEvent) -> None:
        if self.cache_event is None:
            self.cache_event = event
            return
        if event.timestamp < self.cache_event.timestamp:
            raise RuntimeError(
                f"时光回溯：{event}早于{self.cache_event}，引擎将停止运行。"
            )
        self.cache_event = event