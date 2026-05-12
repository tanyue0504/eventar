"""针对 src/eventar/kernel/engine.py 的单元测试。"""
from __future__ import annotations

import dataclasses

import pytest

from eventar.kernel import Event, EventEngine, Phase


@dataclasses.dataclass(frozen=True, slots=True)
class PingEvent(Event):
    seq: int


@dataclasses.dataclass(frozen=True, slots=True)
class PongEvent(Event):
    seq: int


@dataclasses.dataclass(frozen=True, slots=True)
class SpecialPingEvent(PingEvent):
    """PingEvent 的子类，用于测试 MRO 路由。"""


@dataclasses.dataclass(frozen=True, slots=True)
class VerySpecialPingEvent(SpecialPingEvent):
    """SpecialPingEvent 的子类，用于测试多层 MRO 路由顺序。"""


# ---------------------------------------------------------------------------
# 基础派发
# ---------------------------------------------------------------------------

def test_immediate_dispatch_when_idle() -> None:
    engine = EventEngine()
    seen: list[int] = []

    def on_ping(event: Event) -> None:
        assert isinstance(event, PingEvent)
        seen.append(event.seq)

    engine.register(PingEvent, on_ping)
    engine.push(PingEvent(seq=1))

    assert seen == [1]


def test_unregistered_event_triggers_nothing() -> None:
    engine = EventEngine()
    seen: list[str] = []
    engine.register(PingEvent, lambda e: seen.append("ping"))
    engine.push(PongEvent(seq=1))
    assert seen == []


# ---------------------------------------------------------------------------
# MRO 路由（子类触发父类监听器）
# ---------------------------------------------------------------------------

def test_subclass_event_triggers_parent_listener() -> None:
    """注册在 PingEvent 的监听器能接收 SpecialPingEvent 实例。"""
    engine = EventEngine()
    seen: list[str] = []

    engine.register(PingEvent, lambda e: seen.append(type(e).__name__))
    engine.push(SpecialPingEvent(seq=1))

    assert seen == ["SpecialPingEvent"]


def test_subclass_event_triggers_both_parent_and_self_listener() -> None:
    """子类和父类的监听器均能收到子类事件，父类（MRO 后续）先注册但晚于子类监听器触发。"""
    engine = EventEngine()
    seen: list[str] = []

    # MRO: SpecialPingEvent -> PingEvent -> Event -> object
    engine.register(PingEvent, lambda e: seen.append("ping_listener"))
    engine.register(SpecialPingEvent, lambda e: seen.append("special_listener"))

    engine.push(SpecialPingEvent(seq=1))

    # SpecialPingEvent 在 MRO 中更靠前，先触发；PingEvent 监听器随后
    assert seen == ["special_listener", "ping_listener"]


def test_register_on_event_root_receives_all() -> None:
    """注册在 Event 根类的监听器相当于全局监听，能接收所有事件。"""
    engine = EventEngine()
    seen: list[str] = []

    engine.register(Event, lambda e: seen.append(type(e).__name__))
    engine.push(PingEvent(seq=1))
    engine.push(PongEvent(seq=2))

    assert seen == ["PingEvent", "PongEvent"]


def test_parent_listener_does_not_receive_sibling_events() -> None:
    """PingEvent 监听器不会收到 PongEvent（两者是兄弟类，无继承关系）。"""
    engine = EventEngine()
    seen: list[str] = []

    engine.register(PingEvent, lambda e: seen.append("ping"))
    engine.push(PongEvent(seq=1))

    assert seen == []


def test_multi_level_mro_listener_order() -> None:
    """多层继承时按 MRO 顺序触发：具体类 -> 父类 -> 祖先类。"""
    engine = EventEngine()
    seen: list[str] = []

    engine.register(Event, lambda e: seen.append("event"))
    engine.register(PingEvent, lambda e: seen.append("ping"))
    engine.register(SpecialPingEvent, lambda e: seen.append("special"))
    engine.register(VerySpecialPingEvent, lambda e: seen.append("very_special"))

    engine.push(VerySpecialPingEvent(seq=1))

    assert seen == ["very_special", "special", "ping", "event"]


# ---------------------------------------------------------------------------
# 路由缓存
# ---------------------------------------------------------------------------

def test_route_cache_is_populated_after_dispatch() -> None:
    """派发后缓存中应存有该事件类型的路由条目。"""
    engine = EventEngine()
    engine.register(PingEvent, lambda e: None)
    engine.push(PingEvent(seq=1))
    assert PingEvent in engine._route_cache[Phase.MAIN]


def test_register_clears_route_cache() -> None:
    """新增监听器后，对应 Phase 的路由缓存被清空。"""
    engine = EventEngine()
    engine.register(PingEvent, lambda e: None)
    engine.push(PingEvent(seq=1))
    assert PingEvent in engine._route_cache[Phase.MAIN]

    engine.register(PingEvent, lambda e: None)
    assert engine._route_cache[Phase.MAIN] == {}


def test_unregister_clears_route_cache() -> None:
    """取消监听器后，对应 Phase 的路由缓存被清空。"""
    engine = EventEngine()
    listener = lambda e: None
    engine.register(PingEvent, listener)
    engine.push(PingEvent(seq=1))
    assert PingEvent in engine._route_cache[Phase.MAIN]

    engine.unregister(PingEvent, listener)
    assert engine._route_cache[Phase.MAIN] == {}


def test_register_clears_only_target_phase_cache() -> None:
    """register 只清空目标 Phase 的缓存，不影响其他 Phase 缓存。"""
    engine = EventEngine()

    engine.register(PingEvent, lambda e: None, Phase.PRE)
    engine.register(PingEvent, lambda e: None, Phase.MAIN)

    engine.push(PingEvent(seq=1))
    assert PingEvent in engine._route_cache[Phase.PRE]
    assert PingEvent in engine._route_cache[Phase.MAIN]

    engine.register(PingEvent, lambda e: None, Phase.PRE)

    assert engine._route_cache[Phase.PRE] == {}
    assert PingEvent in engine._route_cache[Phase.MAIN]


def test_unregister_clears_only_target_phase_cache() -> None:
    """unregister 只清空目标 Phase 的缓存，不影响其他 Phase 缓存。"""
    engine = EventEngine()
    pre_listener = lambda e: None
    main_listener = lambda e: None

    engine.register(PingEvent, pre_listener, Phase.PRE)
    engine.register(PingEvent, main_listener, Phase.MAIN)

    engine.push(PingEvent(seq=1))
    assert PingEvent in engine._route_cache[Phase.PRE]
    assert PingEvent in engine._route_cache[Phase.MAIN]

    engine.unregister(PingEvent, pre_listener, Phase.PRE)

    assert engine._route_cache[Phase.PRE] == {}
    assert PingEvent in engine._route_cache[Phase.MAIN]


# ---------------------------------------------------------------------------
# Phase 顺序
# ---------------------------------------------------------------------------

def test_dispatch_order_pre_main_post() -> None:
    """同一事件在三个 Phase 的触发顺序必须是 PRE → MAIN → POST。"""
    engine = EventEngine()
    order: list[str] = []

    engine.register(PingEvent, lambda e: order.append("main"), Phase.MAIN)
    engine.register(PingEvent, lambda e: order.append("post"), Phase.POST)
    engine.register(PingEvent, lambda e: order.append("pre"), Phase.PRE)

    engine.push(PingEvent(seq=1))

    assert order == ["pre", "main", "post"]


def test_same_phase_respects_registration_order() -> None:
    """同 Phase 内，监听器按注册顺序触发。"""
    engine = EventEngine()
    order: list[int] = []

    engine.register(PingEvent, lambda e: order.append(1))
    engine.register(PingEvent, lambda e: order.append(2))
    engine.register(PingEvent, lambda e: order.append(3))

    engine.push(PingEvent(seq=0))

    assert order == [1, 2, 3]


def test_pre_phase_listener_on_root_event() -> None:
    """注册在 Event 根类 PRE 阶段的监听器，在 MAIN 阶段之前触发。"""
    engine = EventEngine()
    order: list[str] = []

    engine.register(Event, lambda e: order.append("pre:Event"), Phase.PRE)
    engine.register(PingEvent, lambda e: order.append("main:PingEvent"), Phase.MAIN)

    engine.push(PingEvent(seq=1))

    assert order == ["pre:Event", "main:PingEvent"]


# ---------------------------------------------------------------------------
# FIFO 队列行为
# ---------------------------------------------------------------------------

def test_fifo_for_events_pushed_during_dispatch() -> None:
    engine = EventEngine()
    seen: list[int] = []

    def on_ping(event: Event) -> None:
        assert isinstance(event, PingEvent)
        seen.append(event.seq)
        if event.seq == 1:
            engine.push(PingEvent(seq=2))
            engine.push(PingEvent(seq=3))

    engine.register(PingEvent, on_ping)
    engine.push(PingEvent(seq=1))

    assert seen == [1, 2, 3]


def test_event_echo_happens_if_listener_pushes_same_routed_event_type() -> None:
    """监听器 push 的同类事件会再次路由到自己（事件回声）。"""
    engine = EventEngine()
    seen: list[int] = []

    def on_ping(event: Event) -> None:
        assert isinstance(event, PingEvent)
        seen.append(event.seq)
        if event.seq == 1:
            engine.push(PingEvent(seq=2))

    engine.register(PingEvent, on_ping)
    engine.push(PingEvent(seq=1))

    assert seen == [1, 2]


# ---------------------------------------------------------------------------
# unregister 行为
# ---------------------------------------------------------------------------

def test_unregister_stops_listener() -> None:
    engine = EventEngine()
    seen: list[int] = []

    def on_ping(event: Event) -> None:
        seen.append(event.seq)

    engine.register(PingEvent, on_ping)
    engine.unregister(PingEvent, on_ping)
    engine.push(PingEvent(seq=1))

    assert seen == []


def test_unregister_missing_listener_raises_value_error() -> None:
    engine = EventEngine()

    def on_ping(event: Event) -> None:
        _ = event

    with pytest.raises(ValueError):
        engine.unregister(PingEvent, on_ping)


def test_unregister_respects_phase() -> None:
    """从 PRE 阶段注册的监听器，只能从 PRE 阶段注销；从 MAIN 注销会失败。"""
    engine = EventEngine()
    listener = lambda e: None
    engine.register(PingEvent, listener, Phase.PRE)

    with pytest.raises(ValueError):
        engine.unregister(PingEvent, listener, Phase.MAIN)

    # 从正确 Phase 注销不报错
    engine.unregister(PingEvent, listener, Phase.PRE)


# ---------------------------------------------------------------------------
# 直接运行入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
