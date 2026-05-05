"""针对 src/eventar/core/event.py 的单元测试。

测试基类（Event / DataEvent / LogicEvent）时，必须有具体的子类实例，
因为基类本身无法覆盖字段读写、slots、继承等行为。这里在模块顶部定义
BarEvent / SignalEvent 作为测试专用的最小实现，这是 pytest 的标准做法，
不影响生产代码，也不需要改变测试结构。
"""
from __future__ import annotations

import dataclasses

import pytest

from eventar.core.event import DataEvent, Event, LogicEvent

# ---------------------------------------------------------------------------
# 测试专用最小子类
# 定义在模块级：fixture 适合管理实例，类定义本身放在模块顶部更简洁清晰。
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True, slots=True)
class BarEvent(DataEvent):
    code: str
    close: float


@dataclasses.dataclass(frozen=True, slots=True)
class SignalEvent(LogicEvent):
    direction: int


# ---------------------------------------------------------------------------
# fixtures — 提供常用实例，避免各测试函数重复构造
# ---------------------------------------------------------------------------

@pytest.fixture
def bar():
    return BarEvent(timestamp=1_704_153_000_000_000_000, code="000001.SZ", close=10.2)


@pytest.fixture
def signal():
    return SignalEvent(direction=1)


# ---------------------------------------------------------------------------
# 1. 实例化
# ---------------------------------------------------------------------------

def test_event_base_instantiates():
    """Event 基类本身可以直接实例化。"""
    assert isinstance(Event(), Event)


def test_data_event_base_instantiates():
    """DataEvent 基类可以直接实例化。"""
    assert isinstance(DataEvent(timestamp=1_000_000), DataEvent)


def test_logic_event_base_instantiates():
    """LogicEvent 基类可以直接实例化。"""
    assert isinstance(LogicEvent(), LogicEvent)


def test_concrete_data_event_instantiates(bar):
    """具体 DataEvent 子类字段值与构造参数一致。"""
    assert bar.code == "000001.SZ"
    assert bar.close == 10.2


def test_concrete_logic_event_instantiates(signal):
    """具体 LogicEvent 子类字段值与构造参数一致。"""
    assert signal.direction == 1


# ---------------------------------------------------------------------------
# 2. frozen — 写入字段应立即报错
# ---------------------------------------------------------------------------

def test_event_frozen_flag():
    """Event 的 __dataclass_params__.frozen 为 True。

    注意：对 frozen+slots 类写入不存在的属性时，CPython 内部 super() 单元格
    对齐问题会触发 TypeError 而非 FrozenInstanceError。因此通过元数据验证
    frozen 约束，而非直接写入不存在的属性。
    """
    assert Event.__dataclass_params__.frozen is True


def test_data_event_timestamp_immutable():
    """DataEvent.timestamp 不可被修改。"""
    d = DataEvent(timestamp=100)
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.timestamp = 200  # type: ignore[misc]


def test_bar_event_field_immutable(bar):
    """BarEvent.close 不可被修改。"""
    with pytest.raises(dataclasses.FrozenInstanceError):
        bar.close = 0.0  # type: ignore[misc]


def test_signal_event_field_immutable(signal):
    """SignalEvent.direction 不可被修改。"""
    with pytest.raises(dataclasses.FrozenInstanceError):
        signal.direction = 0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 3. timestamp 字段可访问
# ---------------------------------------------------------------------------

def test_data_event_timestamp_readable():
    ts = 1_704_153_000_000_000_000
    assert DataEvent(timestamp=ts).timestamp == ts


def test_bar_event_timestamp_readable(bar):
    """BarEvent.timestamp 继承自 DataEvent，值与构造参数一致。"""
    assert bar.timestamp == 1_704_153_000_000_000_000


def test_logic_event_has_no_timestamp(signal):
    """LogicEvent 没有 timestamp 字段。"""
    assert not hasattr(signal, "timestamp")


# ---------------------------------------------------------------------------
# 4. slots — 无 __dict__
# ---------------------------------------------------------------------------

def test_event_base_no_dict():
    assert not hasattr(Event(), "__dict__")


def test_data_event_no_dict():
    assert not hasattr(DataEvent(timestamp=0), "__dict__")


def test_logic_event_no_dict():
    assert not hasattr(LogicEvent(), "__dict__")


def test_concrete_event_no_dict(bar):
    assert not hasattr(bar, "__dict__")


def test_dynamic_attribute_blocked(bar):
    """slots 类动态写入未定义属性不可能静默成功。

    frozen+slots 类写入不存在的属性时 CPython 可能抛出
    FrozenInstanceError、AttributeError 或 TypeError，三种都是预期行为。
    """
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError, TypeError)):
        bar.new_attr = "x"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 5. isinstance / 继承链
# ---------------------------------------------------------------------------

def test_bar_is_data_event(bar):
    assert isinstance(bar, DataEvent)


def test_bar_is_event(bar):
    assert isinstance(bar, Event)


def test_signal_is_logic_event(signal):
    assert isinstance(signal, LogicEvent)


def test_signal_is_event(signal):
    assert isinstance(signal, Event)


def test_data_event_not_logic_event(bar):
    assert not isinstance(bar, LogicEvent)


def test_logic_event_not_data_event(signal):
    assert not isinstance(signal, DataEvent)


# ---------------------------------------------------------------------------
# 6. __new__ 约束检查 — 违规子类在实例化时应抛出 TypeError
# ---------------------------------------------------------------------------

def test_missing_dataclass_decorator_raises():
    """子类缺少 @dataclass 装饰器，实例化时应报 TypeError。"""
    class BadEvent(Event):
        pass

    with pytest.raises(TypeError, match="@dataclass|装饰"):
        BadEvent()


def test_missing_slots_raises():
    """子类设置 slots=False，实例化时应报 TypeError。"""
    @dataclasses.dataclass(frozen=True, slots=False)
    class NoSlots(Event):
        pass

    with pytest.raises(TypeError, match="slots=True"):
        NoSlots()


def test_frozen_false_rejected_at_class_definition():
    """frozen=False 继承 frozen 父类，Python 在类定义阶段即拒绝。"""
    with pytest.raises(TypeError):
        @dataclasses.dataclass(frozen=False, slots=True)
        class NotFrozen(Event):
            pass


# ---------------------------------------------------------------------------
# 7. 相等性与哈希（frozen dataclass 自动生成 __eq__ 和 __hash__）
# ---------------------------------------------------------------------------

def test_equal_instances():
    assert BarEvent(timestamp=1, code="A", close=1.0) == BarEvent(timestamp=1, code="A", close=1.0)


def test_unequal_instances():
    assert BarEvent(timestamp=1, code="A", close=1.0) != BarEvent(timestamp=1, code="A", close=2.0)


def test_hashable(bar, signal):
    """frozen dataclass 可用作字典键。"""
    d = {bar: "bar_val", signal: "sig_val"}
    assert d[bar] == "bar_val"
    assert d[signal] == "sig_val"


def test_usable_as_set_element():
    a = BarEvent(timestamp=1, code="A", close=1.0)
    b = BarEvent(timestamp=1, code="A", close=1.0)
    c = BarEvent(timestamp=2, code="B", close=2.0)
    assert len({a, b, c}) == 2


# ---------------------------------------------------------------------------
# 8. 路由分发 — 用类对象作键
# ---------------------------------------------------------------------------

def test_type_as_dict_key():
    """type(event) 可直接用作 dict 键，按类对象分发，无需字符串标识。"""
    results = []
    handlers = {
        BarEvent: lambda e: results.append(f"bar:{e.code}"),
        SignalEvent: lambda e: results.append(f"signal:{e.direction}"),
    }
    events = [
        BarEvent(timestamp=1, code="000001.SZ", close=10.0),
        SignalEvent(direction=1),
        BarEvent(timestamp=2, code="000002.SZ", close=20.0),
    ]
    for event in events:
        handlers[type(event)](event)

    assert results == ["bar:000001.SZ", "signal:1", "bar:000002.SZ"]


# ---------------------------------------------------------------------------
# 直接运行入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
