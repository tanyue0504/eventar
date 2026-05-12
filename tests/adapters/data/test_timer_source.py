"""TimerSource 测试。"""
from __future__ import annotations

from eventar.adapters.data import TimerSource
from eventar.data import DataEvent, TimerEvent
from eventar.kernel import EventEngine, Phase


def test_timer_source_yields_timer_event_instances():
    events = list(TimerSource(0, 3))
    assert all(isinstance(e, TimerEvent) for e in events)
    assert all(isinstance(e, DataEvent) for e in events)


def test_timer_source_yields_expected_timestamps():
    source = TimerSource(10, 15)
    assert [e.timestamp for e in source] == [10, 11, 12, 13, 14]


def test_timer_source_honors_step():
    source = TimerSource(0, 10, step=3)
    assert [e.timestamp for e in source] == [0, 3, 6, 9]


def test_timer_source_empty_when_range_empty():
    assert list(TimerSource(5, 5)) == []
    assert list(TimerSource(9, 2)) == []


def test_timer_source_is_repeatable_iterable():
    source = TimerSource(1, 4)
    assert [e.timestamp for e in source] == [1, 2, 3]
    assert [e.timestamp for e in source] == [1, 2, 3]


def test_timer_source_events_route_to_dataevent_listener() -> None:
    """TimerSource 产出的 TimerEvent 应能命中 DataEvent 监听器（MRO 路由）。"""
    engine = EventEngine()
    seen: list[int] = []

    engine.register(DataEvent, lambda e: seen.append(e.timestamp))

    for event in TimerSource(10, 13):
        engine.push(event)

    assert seen == [10, 11, 12]


def test_timer_source_events_respect_phase_order() -> None:
    """TimerSource 事件进入引擎后，监听器触发顺序应为 PRE -> MAIN -> POST。"""
    engine = EventEngine()
    seen: list[str] = []

    engine.register(TimerEvent, lambda e: seen.append("main"), Phase.MAIN)
    engine.register(TimerEvent, lambda e: seen.append("post"), Phase.POST)
    engine.register(TimerEvent, lambda e: seen.append("pre"), Phase.PRE)

    engine.push(next(iter(TimerSource(0, 1))))

    assert seen == ["pre", "main", "post"]
