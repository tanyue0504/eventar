"""TimeGuard 测试。

覆盖场景：
- TimeGuard 是 Component 的子类
- start 将 on_dataevent 注册到 PRE 阶段的 DataEvent 路由
- stop 将 on_dataevent 从 PRE 阶段路由中移除
- 第一个事件始终通过（写入缓存）
- 时间戳单调递增时不报错
- 时间戳相等时不报错（仅严格回溯才报错）
- 时间戳回溯时抛出 RuntimeError
- stop 后不再响应新事件
- 非 DataEvent 事件不会被路由到守卫
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from eventar.backtest.guards import MonotonicTimeGuard
from eventar.data import DataEvent
from eventar.kernel import Event, EventEngine, Phase


# ---------------------------------------------------------------------------
# 辅助类型
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Tick(DataEvent):
    pass


@dataclass(frozen=True, slots=True)
class Signal(Event):
    """非 DataEvent 的普通事件。"""
    value: int


# ---------------------------------------------------------------------------
# 基础结构
# ---------------------------------------------------------------------------


def test_time_guard_is_component():
    from eventar.kernel import Component
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    assert isinstance(guard, Component)


def test_start_registers_global_pre():
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    guard.start()
    assert guard.on_dataevent in engine._listeners[Phase.PRE].get(DataEvent, [])


def test_stop_unregisters_global_pre():
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    guard.start()
    guard.stop()
    assert guard.on_dataevent not in engine._listeners[Phase.PRE].get(DataEvent, [])


# ---------------------------------------------------------------------------
# 通过 engine.push 验证守卫行为
# ---------------------------------------------------------------------------


def test_first_event_sets_cache():
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    guard.start()
    e = Tick(timestamp=10)
    engine.push(e)
    assert guard.cache_event is e


def test_monotonic_timestamps_no_error():
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    guard.start()
    for ts in [1, 2, 5, 10, 100]:
        engine.push(Tick(timestamp=ts))  # 不应抛出


def test_equal_timestamps_no_error():
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    guard.start()
    engine.push(Tick(timestamp=5))
    engine.push(Tick(timestamp=5))  # 相等不算回溯


def test_backwards_timestamp_raises():
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    guard.start()
    engine.push(Tick(timestamp=10))
    with pytest.raises(RuntimeError):
        engine.push(Tick(timestamp=9))


def test_error_message_mentions_events():
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    guard.start()
    first = Tick(timestamp=10)
    second = Tick(timestamp=5)
    engine.push(first)
    with pytest.raises(RuntimeError, match="时光回溯"):
        engine.push(second)


def test_non_data_event_after_first_is_ignored_in_engine_routing():
    """非 DataEvent 不会路由到守卫，缓存保持不变。"""
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    guard.start()

    first = Tick(timestamp=10)
    engine.push(first)
    engine.push(Signal(value=99))

    assert guard.cache_event is first


def test_non_data_event_as_first_event_is_ignored():
    """首个非 DataEvent 不应写入缓存，避免后续比较时报错。"""
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    guard.start()
    engine.push(Signal(value=1))
    assert guard.cache_event is None
    engine.push(Tick(timestamp=10))
    assert guard.cache_event == Tick(timestamp=10)


# ---------------------------------------------------------------------------
# 集成：通过 EventEngine.push 触发
# ---------------------------------------------------------------------------


def test_integrated_monotonic_sequence_no_error():
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    guard.start()
    for ts in [0, 1, 2, 3]:
        engine.push(Tick(timestamp=ts))  # 不应抛出


def test_integrated_backwards_raises_from_push():
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    guard.start()
    engine.push(Tick(timestamp=10))
    with pytest.raises(RuntimeError):
        engine.push(Tick(timestamp=5))


def test_after_stop_backwards_does_not_raise():
    """stop 后监听器已移除，时光回溯也不再检测。"""
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    guard.start()
    engine.push(Tick(timestamp=10))
    guard.stop()
    engine.push(Tick(timestamp=1))  # 不再受守卫约束
