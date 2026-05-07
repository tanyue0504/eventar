
from dataclasses import dataclass

from eventar.kernel.event import Event

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