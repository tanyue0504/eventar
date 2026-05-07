"""针对 src/eventar/kernel/event.py 的单元测试。"""
from __future__ import annotations

import dataclasses

import pytest

from eventar.data import DataEvent
from eventar.kernel import Event


@dataclasses.dataclass(frozen=True, slots=True)
class SignalEvent(Event):
    direction: int


@dataclasses.dataclass(frozen=True, slots=True)
class KernelEvent(Event):
    name: str


@pytest.fixture
def signal():
    return SignalEvent(direction=1)


def test_event_base_instantiates():
    assert isinstance(Event(), Event)


def test_event_subclass_instantiates():
    assert isinstance(SignalEvent(direction=1), SignalEvent)


def test_concrete_logic_event_instantiates(signal):
    assert signal.direction == 1


def test_event_frozen_flag():
    assert Event.__dataclass_params__.frozen is True


def test_signal_event_field_immutable(signal):
    with pytest.raises(dataclasses.FrozenInstanceError):
        signal.direction = 0  # type: ignore[misc]


def test_event_subclass_has_no_timestamp(signal):
    assert not hasattr(signal, "timestamp")


def test_event_base_no_dict():
    assert not hasattr(Event(), "__dict__")


def test_event_subclass_no_dict(signal):
    assert not hasattr(signal, "__dict__")


def test_dynamic_attribute_blocked(signal):
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError, TypeError)):
        signal.new_attr = "x"  # type: ignore[attr-defined]


def test_signal_is_its_own_type(signal):
    assert isinstance(signal, SignalEvent)


def test_signal_is_event(signal):
    assert isinstance(signal, Event)


def test_event_subclass_not_data_event(signal):
    assert not isinstance(signal, DataEvent)


def test_missing_dataclass_decorator_raises():
    class BadEvent(Event):
        pass

    with pytest.raises(TypeError, match="@dataclass|装饰"):
        BadEvent()


def test_missing_slots_raises():
    @dataclasses.dataclass(frozen=True, slots=False)
    class NoSlots(Event):
        pass

    with pytest.raises(TypeError, match="slots=True"):
        NoSlots()


def test_frozen_false_rejected_at_class_definition():
    with pytest.raises(TypeError):
        @dataclasses.dataclass(frozen=False, slots=True)
        class NotFrozen(Event):
            pass


def test_type_as_dict_key():
    results = []
    handlers = {
        SignalEvent: lambda e: results.append(f"signal:{e.direction}"),
        KernelEvent: lambda e: results.append(f"kernel:{e.name}"),
    }
    events = [SignalEvent(direction=1), KernelEvent(name="K")]
    for event in events:
        handlers[type(event)](event)

    assert results == ["signal:1", "kernel:K"]
