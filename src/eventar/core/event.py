"""事件基类层次定义。

设计约束（详见 docs/adr/1-event&engine.md）：
- 所有事件类必须使用 @dataclass(frozen=True, slots=True) 装饰。
- 引擎在事件构造完成后不会写入任何字段。
- 三个基类覆盖两种语义域：
    Event       -> 通用根基类，无字段
    DataEvent   -> 市场数据事件，携带必填 timestamp 字段
    LogicEvent  -> 策略逻辑事件，无强制字段
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass


def _assert_frozen_slots_dataclass(cls: type) -> None:
    """检查 cls 是否满足 frozen=True 且 slots=True 的 dataclass 约束。

    在 Event.__new__ 中调用，以便在实例化时立即发现违规的子类定义。

    注意：使用 ``"__dataclass_params__" in cls.__dict__`` 而非
    ``dataclasses.is_dataclass(cls)``。后者会通过继承返回 True，导致
    未加 ``@dataclass`` 的子类错误地通过 dataclass 检查。
    """
    if "__dataclass_params__" not in cls.__dict__:
        raise TypeError(
            f"{cls.__name__} 必须用 @dataclass 装饰后才能实例化。"
        )
    if not cls.__dataclass_params__.frozen:
        raise TypeError(
            f"{cls.__name__} 必须设置 frozen=True。"
        )
    # slots=True 会在类自身的 __dict__ 中写入 __slots__；
    # 若只有父类有 __slots__ 而本类未设置，则说明遗漏了 slots=True。
    if "__slots__" not in cls.__dict__:
        raise TypeError(
            f"{cls.__name__} 必须设置 slots=True。"
        )


@dataclass(frozen=True, slots=True)
class Event:
    """事件层次的根基类，本身无任何字段。

    所有事件的公共基类，提供 frozen + slots 约束。
    三个基类（Event / DataEvent / LogicEvent）均可直接实例化，
    不使用 ABC，避免强迫子类实现无意义的抽象方法。

    子类约束
    --------
    - 必须使用 ``@dataclass(frozen=True, slots=True)`` 装饰。
    - 禁止在 ``__post_init__`` 之外通过 ``object.__setattr__`` 绕过 frozen。
    - 所有字段必须有明确的类型标注，不允许使用 ``Any``。

    违反以上约束时，实例化会抛出 ``TypeError``。

    路由分发
    --------
    引擎按事件类型分发时，直接使用类对象作为键：

    ::

        handlers: dict[type[Event], Callable] = {
            BarEvent: on_bar,
            SignalEvent: on_signal,
        }
        handler = handlers[type(event)]

    不使用字符串标识，避免拼写错误和额外的命名约定负担。
    """

    def __new__(cls, *args, **kwargs):
        # 在分配内存之前校验子类约束，保证违规定义在第一次实例化时即被发现。
        # 注意：不能在 __init_subclass__ 中做此检查——那时 @dataclass 装饰器
        # 尚未运行，cls 还不是 dataclass。
        #
        # 注意：不使用 super().__new__(cls)。slots=True 时 @dataclass 会构造一个
        # 全新的类对象，导致 __class__ 隐式单元格指向旧类，super() 校验失败。
        # 直接调用 object.__new__(cls) 可绕开此问题。
        _assert_frozen_slots_dataclass(cls)
        return object.__new__(cls)


@dataclass(frozen=True, slots=True)
class DataEvent(Event):
    """市场数据事件的基类。

    数据事件代表来自行情源的观测——K 线快照、逐笔成交、资金费率等。
    每个数据事件携带一个 ``timestamp`` 字段，表示**数据在来源处生成的时间**。
    引擎转发事件时不修改任何字段，因此 timestamp 始终是原始来源时间戳。

    字段
    ----
    timestamp : int
        数据时间点，纳秒整数时间戳。具体子类可以收窄类型。

    示例
    ----
    ::

        @dataclass(frozen=True, slots=True)
        class BarEvent(DataEvent):
            code: str
            open: float
            high: float
            low: float
            close: float
            vol: int
            amount: float

        bar = BarEvent(
            timestamp=1704153000_000_000_000,
            code="000001.SZ",
            open=10.0, high=10.5, low=9.8, close=10.2,
            vol=1_000_000, amount=10_200_000.0,
        )
        bar.close = 11.0  # 立即抛出 FrozenInstanceError
    """

    timestamp: int


@dataclass(frozen=True, slots=True)
class LogicEvent(Event):
    """策略逻辑事件的基类。

    逻辑事件代表策略组件生成的决策——信号、委托指令、撤单、仓位调整等。
    它们描述"应该发生什么"，而非"何时观测到数据"，因此本级不强制携带时间戳。

    具体子类如需记录决策时间，可自行添加 timestamp 字段，但不作强制要求。

    示例
    ----
    ::

        @dataclass(frozen=True, slots=True)
        class SignalEvent(LogicEvent):
            code: str
            direction: int    # +1 做多 / -1 做空 / 0 平仓
            strength: float

        @dataclass(frozen=True, slots=True)
        class OrderEvent(LogicEvent):
            code: str
            quantity: int
            price: float
            side: str         # "buy" 或 "sell"
    """
