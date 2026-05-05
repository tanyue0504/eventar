"""Component 抽象基类测试。

覆盖场景：
- ABC 约束：未实现 start/stop 的子类不能实例化
- 生命周期：start/stop 被调用时子类逻辑执行
"""
from __future__ import annotations

import pytest

from eventar.core.component import Component
from eventar.core.engine import EventEngine


# ---------------------------------------------------------------------------
# 具体组件
# ---------------------------------------------------------------------------


class LifecycleComponent(Component):
    """记录 start/stop 调用次数的最小组件。"""

    def __init__(self, engine: EventEngine) -> None:
        super().__init__(engine)
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1


# ---------------------------------------------------------------------------
# 测试夹具
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine() -> EventEngine:
    return EventEngine()


# ---------------------------------------------------------------------------
# ABC 约束
# ---------------------------------------------------------------------------


def test_component_is_abstract():
    """Component 不能直接实例化。"""
    with pytest.raises(TypeError):
        Component(EventEngine())  # type: ignore[abstract]


def test_component_missing_start_is_abstract():
    """只实现 stop 的子类仍不能实例化。"""

    class OnlyStop(Component):
        def stop(self) -> None:
            pass

    with pytest.raises(TypeError):
        OnlyStop(EventEngine())  # type: ignore[abstract]


def test_component_missing_stop_is_abstract():
    """只实现 start 的子类仍不能实例化。"""

    class OnlyStart(Component):
        def start(self) -> None:
            pass

    with pytest.raises(TypeError):
        OnlyStart(EventEngine())  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# 生命周期
# ---------------------------------------------------------------------------


def test_start_stop_called(engine):
    """start/stop 各被调用一次时计数正确。"""
    comp = LifecycleComponent(engine)
    comp.start()
    comp.stop()
    assert comp.started == 1
    assert comp.stopped == 1


def test_start_stop_multiple_times(engine):
    """多次 start/stop 均被执行。"""
    comp = LifecycleComponent(engine)
    comp.start()
    comp.start()
    comp.stop()
    assert comp.started == 2
    assert comp.stopped == 1


if __name__ == "__main__":
    import pytest as _pytest

    _pytest.main([__file__, "-v"])
