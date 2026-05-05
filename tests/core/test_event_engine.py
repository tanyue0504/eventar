"""针对 src/eventar/core/engine.py 的单元测试。"""
from __future__ import annotations

import dataclasses

import pytest

from eventar.core.engine import EventEngine
from eventar.core.event import Event, LogicEvent


@dataclasses.dataclass(frozen=True, slots=True)
class PingEvent(LogicEvent):
    seq: int


@dataclasses.dataclass(frozen=True, slots=True)
class PongEvent(LogicEvent):
    seq: int


def test_dispatch_order_pre_typed_post() -> None:
    engine = EventEngine()
    order: list[str] = []

    def on_pre(event: Event) -> None:
        order.append(f"pre:{type(event).__name__}")

    def on_ping(event: Event) -> None:
        order.append(f"typed:{type(event).__name__}")

    def on_post(event: Event) -> None:
        order.append(f"post:{type(event).__name__}")

    engine.register_global_pre(on_pre)
    engine.register_for(PingEvent, on_ping)
    engine.register_global_post(on_post)

    engine.push(PingEvent(seq=1))

    assert order == ["pre:PingEvent", "typed:PingEvent", "post:PingEvent"]


def test_immediate_dispatch_when_idle() -> None:
    engine = EventEngine()
    seen: list[int] = []

    def on_ping(event: Event) -> None:
        assert isinstance(event, PingEvent)
        seen.append(event.seq)

    engine.register_for(PingEvent, on_ping)
    engine.push(PingEvent(seq=1))

    assert seen == [1]


def test_fifo_for_events_pushed_during_dispatch() -> None:
    engine = EventEngine()
    seen: list[int] = []

    def on_ping(event: Event) -> None:
        assert isinstance(event, PingEvent)
        seen.append(event.seq)
        if event.seq == 1:
            engine.push(PingEvent(seq=2))
            engine.push(PingEvent(seq=3))

    engine.register_for(PingEvent, on_ping)
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

    engine.register_for(PingEvent, on_ping)
    engine.push(PingEvent(seq=1))

    assert seen == [1, 2]


def test_type_routing_is_exact_not_base_class() -> None:
    engine = EventEngine()
    seen: list[str] = []

    def on_logic(event: Event) -> None:
        seen.append(f"logic:{type(event).__name__}")

    def on_ping(event: Event) -> None:
        seen.append(f"ping:{type(event).__name__}")

    engine.register_for(LogicEvent, on_logic)
    engine.register_for(PingEvent, on_ping)

    engine.push(PingEvent(seq=1))
    engine.push(PongEvent(seq=2))

    # 当前实现是按 type(event) 精确匹配，不按继承树广播。
    assert seen == ["ping:PingEvent"]


def test_unregister_global_pre_listener() -> None:
    engine = EventEngine()
    seen: list[str] = []

    def on_pre(event: Event) -> None:
        seen.append(f"pre:{type(event).__name__}")

    engine.register_global_pre(on_pre)
    engine.unregister_global_pre(on_pre)

    engine.push(PingEvent(seq=1))

    assert seen == []


def test_unregister_typed_listener() -> None:
    engine = EventEngine()
    seen: list[str] = []

    def on_ping(event: Event) -> None:
        seen.append(f"typed:{type(event).__name__}")

    engine.register_for(PingEvent, on_ping)
    engine.unregister_for(PingEvent, on_ping)

    engine.push(PingEvent(seq=1))

    assert seen == []


def test_unregister_global_post_listener() -> None:
    engine = EventEngine()
    seen: list[str] = []

    def on_post(event: Event) -> None:
        seen.append(f"post:{type(event).__name__}")

    engine.register_global_post(on_post)
    engine.unregister_global_post(on_post)

    engine.push(PingEvent(seq=1))

    assert seen == []


def test_unregister_missing_listener_raises_value_error() -> None:
    """当前实现使用 list.remove，删除未注册监听会抛 ValueError。"""
    engine = EventEngine()

    def on_ping(event: Event) -> None:
        _ = event

    with pytest.raises(ValueError):
        engine.unregister_for(PingEvent, on_ping)

    with pytest.raises(ValueError):
        engine.unregister_global_pre(on_ping)

    with pytest.raises(ValueError):
        engine.unregister_global_post(on_ping)


# ---------------------------------------------------------------------------
# 直接运行入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
