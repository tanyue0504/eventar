"""事件引擎内核模块。

包含事件基类、事件引擎、组件抽象基类等核心基础设施。
"""

from eventar.kernel.event import Event
from eventar.kernel.engine import EventEngine, EventListener, Phase
from eventar.kernel.component import Component

__all__ = ["Component", "Event", "EventEngine", "EventListener", "Phase"]
