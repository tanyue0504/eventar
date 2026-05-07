"""回测引擎。

BacktestEngine 编排完整的回测生命周期：
1. ``add_component`` / ``remove_component`` 管理组件集合；
2. ``run`` 按顺序启动所有组件，驱动 DataEventSource 将事件逐一推入
   EventEngine，数据耗尽后按顺序停止所有组件。
"""
from __future__ import annotations

from eventar.data import DataEventSource
from eventar.kernel import Component, EventEngine


class BacktestEngine:
    """单线程回测引擎。

    Parameters
    ----------
    source:
        数据事件源，``run`` 期间被迭代。

    Attributes
    ----------
    engine:
        内置事件引擎，供外部构造 Component 时注入。
    """

    def __init__(self, source: DataEventSource) -> None:
        self._source = source
        self.engine: EventEngine = EventEngine()
        self._components: list[Component] = []

    # ------------------------------------------------------------------
    # 组件管理
    # ------------------------------------------------------------------

    def add_component(self, component: Component) -> None:
        """在组件列表末尾追加组件。"""
        self._components.append(component)

    def remove_component(self, component: Component) -> None:
        """从组件列表中移除组件。"""
        self._components.remove(component)

    # ------------------------------------------------------------------
    # 回测驱动
    # ------------------------------------------------------------------

    def run(self) -> None:
        """启动回测。

        执行步骤：

        1. 按顺序调用所有组件的 ``start``；
        2. 遍历数据源，将每个 DataEvent 推入事件引擎；
        3. 按顺序调用所有组件的 ``stop``。
        """
        for component in self._components:
            component.start()

        try:
            for event in self._source:
                self.engine.push(event)
        finally:
            for component in self._components:
                component.stop()
