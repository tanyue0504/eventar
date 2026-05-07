"""数据处理抽象层。

包含数据加载器、数据事件、数据事件源等数据处理的抽象接口。
"""

from eventar.data.event import DataEvent, TimerEvent
from eventar.data.loader import DataLoader
from eventar.data.source import DataEventSource

__all__ = ["DataEvent", "TimerEvent", "DataEventSource", "DataLoader"]
