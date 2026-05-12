"""针对 src/eventar/data/event.py 的单元测试。"""
from __future__ import annotations

import dataclasses

import pytest

from eventar.data import DataEvent, TimerEvent
from eventar.kernel import Event, EventEngine, Phase


@dataclasses.dataclass(frozen=True, slots=True)
class BarEvent(DataEvent):
    code: str
    close: float


@dataclasses.dataclass(frozen=True, slots=True)
class KernelEvent(Event):
    name: str


@pytest.fixture
def bar():
    return BarEvent(timestamp=1_704_153_000_000_000_000, code="000001.SZ", close=10.2)


@pytest.fixture
def kernel_event():
    return KernelEvent(name="sig")


def test_data_event_base_instantiates():
    assert isinstance(DataEvent(timestamp=1_000_000), DataEvent)


def test_concrete_data_event_instantiates(bar):
    assert bar.code == "000001.SZ"
    assert bar.close == 10.2


def test_data_event_timestamp_immutable():
    d = DataEvent(timestamp=100)
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.timestamp = 200  # type: ignore[misc]


def test_bar_event_field_immutable(bar):
    with pytest.raises(dataclasses.FrozenInstanceError):
        bar.close = 0.0  # type: ignore[misc]


def test_data_event_timestamp_readable():
    ts = 1_704_153_000_000_000_000
    assert DataEvent(timestamp=ts).timestamp == ts


def test_bar_event_timestamp_readable(bar):
    assert bar.timestamp == 1_704_153_000_000_000_000


def test_data_event_no_dict():
    assert not hasattr(DataEvent(timestamp=0), "__dict__")


def test_concrete_event_no_dict(bar):
    assert not hasattr(bar, "__dict__")


def test_bar_is_data_event(bar):
    assert isinstance(bar, DataEvent)


def test_bar_is_event(bar):
    assert isinstance(bar, Event)


def test_data_event_not_other_event_subclass(bar):
    assert not isinstance(bar, KernelEvent)


def test_equal_instances():
    assert BarEvent(timestamp=1, code="A", close=1.0) == BarEvent(timestamp=1, code="A", close=1.0)


def test_unequal_instances():
    assert BarEvent(timestamp=1, code="A", close=1.0) != BarEvent(timestamp=1, code="A", close=2.0)


def test_hashable(bar, kernel_event):
    d = {bar: "bar_val", kernel_event: "sig_val"}
    assert d[bar] == "bar_val"
    assert d[kernel_event] == "sig_val"


def test_usable_as_set_element():
    a = BarEvent(timestamp=1, code="A", close=1.0)
    b = BarEvent(timestamp=1, code="A", close=1.0)
    c = BarEvent(timestamp=2, code="B", close=2.0)
    assert len({a, b, c}) == 2


def test_timer_event_is_data_event():
    e = TimerEvent(timestamp=123)
    assert isinstance(e, DataEvent)


def test_timer_event_timestamp_readable():
    e = TimerEvent(timestamp=321)
    assert e.timestamp == 321


def test_timer_event_is_frozen():
    e = TimerEvent(timestamp=1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.timestamp = 2  # type: ignore[misc]


def test_dataevent_listener_receives_timer_event_via_mro_routing():
    """注册在 DataEvent 的监听器应能接收其子类 TimerEvent。"""
    engine = EventEngine()
    seen: list[int] = []

    engine.register(DataEvent, lambda e: seen.append(e.timestamp))
    engine.push(TimerEvent(timestamp=42))

    assert seen == [42]


def test_dataevent_phase_order_pre_main_post():
    """DataEvent 在新引擎中应遵循 PRE -> MAIN -> POST 顺序。"""
    engine = EventEngine()
    seen: list[str] = []

    engine.register(DataEvent, lambda e: seen.append("main"), Phase.MAIN)
    engine.register(DataEvent, lambda e: seen.append("post"), Phase.POST)
    engine.register(DataEvent, lambda e: seen.append("pre"), Phase.PRE)

    engine.push(BarEvent(timestamp=1, code="000001.SZ", close=10.0))

    assert seen == ["pre", "main", "post"]
