"""TimeGuard 测试。

覆盖场景：
- TimeGuard 是 Component 的子类
- start 将 on_event 注册为全局优先监听器
- stop 将 on_event 从全局优先监听器中移除
- 第一个事件始终通过（写入缓存）
- 时间戳单调递增时不报错
- 时间戳相等时不报错（仅严格回溯才报错）
- 时间戳回溯时抛出 RuntimeError
- stop 后不再响应新事件
- 非 DataEvent 事件在首个事件后不更新缓存，但不报错
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from eventar.backtest.guards import MonotonicTimeGuard
from eventar.data import DataEvent
from eventar.kernel import Event, EventEngine


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
    assert guard.on_event in engine._global_pre_listeners


def test_stop_unregisters_global_pre():
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    guard.start()
    guard.stop()
    assert guard.on_event not in engine._global_pre_listeners


# ---------------------------------------------------------------------------
# on_event 行为
# ---------------------------------------------------------------------------


def test_first_event_sets_cache():
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    e = Tick(timestamp=10)
    guard.on_event(e)
    assert guard.cache_event is e


def test_monotonic_timestamps_no_error():
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    for ts in [1, 2, 5, 10, 100]:
        guard.on_event(Tick(timestamp=ts))  # 不应抛出


def test_equal_timestamps_no_error():
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    guard.on_event(Tick(timestamp=5))
    guard.on_event(Tick(timestamp=5))  # 相等不算回溯


def test_backwards_timestamp_raises():
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    guard.on_event(Tick(timestamp=10))
    with pytest.raises(RuntimeError):
        guard.on_event(Tick(timestamp=9))


def test_error_message_mentions_events():
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    first = Tick(timestamp=10)
    second = Tick(timestamp=5)
    guard.on_event(first)
    with pytest.raises(RuntimeError, match="时光回溯"):
        guard.on_event(second)


def test_non_data_event_after_first_does_not_update_cache():
    """非 DataEvent 不更新缓存，后续 DataEvent 仍与原缓存比较。"""
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    first = Tick(timestamp=10)
    guard.on_event(first)
    guard.on_event(Signal(value=99))  # 非 DataEvent，不更新缓存
    assert guard.cache_event is first


def test_non_data_event_as_first_event_is_ignored():
    """首个非 DataEvent 不应写入缓存，避免后续比较时报错。"""
    engine = EventEngine()
    guard = MonotonicTimeGuard(engine)
    guard.on_event(Signal(value=1))
    assert guard.cache_event is None
    guard.on_event(Tick(timestamp=10))
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
