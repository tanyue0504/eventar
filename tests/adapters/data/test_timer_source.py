"""TimerSource 测试。"""
from __future__ import annotations

from eventar.adapters.data import TimerSource
from eventar.data import DataEvent, TimerEvent


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
