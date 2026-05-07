"""BacktestEngine 测试。

覆盖场景：
- run 按顺序调用所有组件的 start
- run 将数据源事件逐一推入事件引擎
- run 数据耗尽后按顺序调用所有组件的 stop
- run 数据源为空时 start/stop 仍被调用
- add_component / remove_component 动态管理组件
- stop 在数据源抛出异常时仍被保证调用（finally 语义）
- engine 属性暴露给外部，供组件构造注入
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import pytest

from eventar.backtest import BacktestEngine
from eventar.data import DataEvent, DataEventSource
from eventar.kernel import Component, EventEngine


# ---------------------------------------------------------------------------
# 辅助类型
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TickEvent(DataEvent):
    value: float


class StubSource(DataEventSource):
    """不依赖真实 DataLoader，直接从列表产出事件。"""

    def __init__(self, events: list[TickEvent]) -> None:
        self._events = events

    def __iter__(self) -> Iterator[TickEvent]:
        yield from self._events


class TrackingComponent(Component):
    """记录 start / stop 调用顺序，兼收集推入引擎的事件。"""

    def __init__(self, engine: EventEngine, name: str) -> None:
        super().__init__(engine)
        self.name = name
        self.calls: list[str] = []
        self.received: list[DataEvent] = []

    def start(self) -> None:
        self.calls.append("start")
        self._engine.register_for(TickEvent, self._on_tick)

    def stop(self) -> None:
        self._engine.unregister_for(TickEvent, self._on_tick)
        self.calls.append("stop")

    def _on_tick(self, event: DataEvent) -> None:
        self.received.append(event)


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------


def make_ticks(*timestamps: int) -> list[TickEvent]:
    return [TickEvent(timestamp=ts, value=float(ts)) for ts in timestamps]


def test_engine_attribute_is_event_engine():
    be = BacktestEngine(StubSource([]))
    assert isinstance(be.engine, EventEngine)


def test_run_calls_start_before_stop():
    be = BacktestEngine(StubSource([]))
    comp = TrackingComponent(be.engine, "c")
    be.add_component(comp)
    be.run()
    assert comp.calls == ["start", "stop"]


def test_run_events_dispatched_to_engine():
    ticks = make_ticks(1, 2, 3)
    be = BacktestEngine(StubSource(ticks))
    comp = TrackingComponent(be.engine, "c")
    be.add_component(comp)
    be.run()
    assert comp.received == ticks


def test_run_empty_source_still_calls_lifecycle():
    be = BacktestEngine(StubSource([]))
    comp = TrackingComponent(be.engine, "c")
    be.add_component(comp)
    be.run()
    assert comp.calls == ["start", "stop"]
    assert comp.received == []


def test_run_start_order_matches_add_order():
    """多个组件时 start 调用顺序与 add_component 顺序一致。"""
    order: list[str] = []

    class OrderedComp(Component):
        def __init__(self, engine: EventEngine, name: str) -> None:
            super().__init__(engine)
            self._name = name

        def start(self) -> None:
            order.append(f"start:{self._name}")

        def stop(self) -> None:
            order.append(f"stop:{self._name}")

    be = BacktestEngine(StubSource([]))
    be.add_component(OrderedComp(be.engine, "A"))
    be.add_component(OrderedComp(be.engine, "B"))
    be.add_component(OrderedComp(be.engine, "C"))
    be.run()
    assert order == ["start:A", "start:B", "start:C", "stop:A", "stop:B", "stop:C"]


def test_remove_component_not_called():
    be = BacktestEngine(StubSource(make_ticks(1, 2)))
    comp_a = TrackingComponent(be.engine, "a")
    comp_b = TrackingComponent(be.engine, "b")
    be.add_component(comp_a)
    be.add_component(comp_b)
    be.remove_component(comp_a)
    be.run()
    assert comp_a.calls == []  # 已移除，不被调用
    assert comp_b.calls == ["start", "stop"]


def test_stop_called_even_if_source_raises():
    """数据源迭代中途抛出异常，stop 仍须被调用（finally）。"""

    class ErrorSource(DataEventSource):
        def __init__(self) -> None:
            pass  # 不调用 super().__init__，覆盖 __iter__ 即可

        def __iter__(self):
            yield TickEvent(timestamp=1, value=1.0)
            raise RuntimeError("source error")

    be = BacktestEngine(ErrorSource())
    comp = TrackingComponent(be.engine, "c")
    be.add_component(comp)
    with pytest.raises(RuntimeError, match="source error"):
        be.run()
    assert "stop" in comp.calls


def test_multiple_components_all_receive_events():
    ticks = make_ticks(10, 20, 30)
    be = BacktestEngine(StubSource(ticks))
    comp1 = TrackingComponent(be.engine, "1")
    comp2 = TrackingComponent(be.engine, "2")
    be.add_component(comp1)
    be.add_component(comp2)
    be.run()
    assert comp1.received == ticks
    assert comp2.received == ticks
