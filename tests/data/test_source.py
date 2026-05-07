"""data.source 模块测试。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from eventar.data.source import DataEventSource
from eventar.data.event import DataEvent


@dataclass(frozen=True, slots=True)
class PriceEvent(DataEvent):
    value: float


class ListSource(DataEventSource):
    def __init__(self, events: list[PriceEvent]) -> None:
        self._events = events

    def __iter__(self) -> Iterator[DataEvent]:
        yield from self._events


def test_source_yields_dataevent_instances():
    """抽象协议下的具体 source 产出对象应是 DataEvent。"""
    source = ListSource([
        PriceEvent(timestamp=1, value=10.0),
        PriceEvent(timestamp=2, value=20.0),
    ])
    for event in source:
        assert isinstance(event, DataEvent)
        assert isinstance(event, PriceEvent)


def test_source_repeatable():
    """同一 DataEventSource 可多次迭代，每次结果相同。"""
    source = ListSource([
        PriceEvent(timestamp=1, value=10.0),
        PriceEvent(timestamp=2, value=20.0),
    ])
    first = list(source)
    second = list(source)
    assert first == second
