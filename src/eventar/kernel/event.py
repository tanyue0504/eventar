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