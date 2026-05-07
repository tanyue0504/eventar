"""组件抽象基类。

所有有状态的可插拔模块（数据源、策略、风控、执行通道等）均应继承 Component。
组件持有 EventEngine 引用（self.engine），子类在 start/stop 中自行调用引擎接口。
生命周期由框架调用 start / stop 管理，子类必须实现这两个方法。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from eventar.kernel.engine import EventEngine


class Component(ABC):
    """组件抽象基类。

    Parameters
    ----------
    engine:
        组件与系统其他部分通信所用的事件引擎实例。

    Subclass Contract
    -----------------
    子类必须实现 ``start`` 与 ``stop`` 方法，分别处理启动和停止逻辑。
    """

    def __init__(self, engine: EventEngine) -> None:
        self.engine = engine

    # ------------------------------------------------------------------
    # 生命周期（子类必须实现）
    # ------------------------------------------------------------------

    @abstractmethod
    def start(self) -> None:
        """启动组件：初始化资源，注册事件监听。"""

    @abstractmethod
    def stop(self) -> None:
        """停止组件：取消事件监听，释放资源。"""