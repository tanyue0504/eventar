"""DataEventSource：将 DataLoader 的 DataFrame 分块转换为 DataEvent 流。

设计要点：
- DataEventSource 是一个 Iterator[DataEvent]，按行逐条生成事件实例。
- 依赖三个构造参数：
    loader      DataLoader 实例，提供 DataFrame 分块。
    columns     列名列表，指定从分块中提取哪些列；列顺序须与 event_type
                构造函数的参数顺序一致（或使用与字段同名的关键字参数）。
    event_type  DataEvent 或其子类的类型对象，用于逐行构造事件。
- transform(chunk) 是可覆盖的钩子方法，在列提取之后、事件构造之前执行，
    默认行为是原样返回分块，子类可在此做单位换算、列重命名、过滤或新增列。
- 支持可重复迭代：每次调用 __iter__ 均会重置内部状态并从头读取 loader。
"""
from __future__ import annotations

from typing import Iterator

import pandas as pd

from eventar.core.data_loader import DataLoader
from eventar.core.event import DataEvent


class DataEventSource:
    """将 DataLoader 产出的 DataFrame 分块逐行转换为 DataEvent 实例。

    Parameters
    ----------
    loader:
        数据加载器，每次迭代产出一个 pd.DataFrame 分块。
    columns:
        从分块中提取的列名列表。列名须与 ``event_type`` 的字段名一一对应，
        提取后的列将以关键字参数形式传入构造函数。
    event_type:
        目标事件类型，必须是 DataEvent 或其子类。
        构造时调用 ``event_type(*row)``，其中 ``row`` 来自 ``to_numpy(copy=False)``
        的单行视图。为保证映射正确，``columns`` 顺序必须与事件字段顺序一致。

    示例
    ----
    ::

        @dataclass(frozen=True, slots=True)
        class BarEvent(DataEvent):
            code: str
            close: float

        loader = CsvDataLoader("bars.csv")
        source = DataEventSource(loader, ["timestamp", "code", "close"], BarEvent)
        for event in source:
            engine.push(event)
    """

    def __init__(
        self,
        loader: DataLoader,
        columns: list[str],
        event_type: type[DataEvent],
    ) -> None:
        self._loader = loader
        self._columns = columns
        self._event_type = event_type

    # ------------------------------------------------------------------
    # 可覆盖的转换钩子
    # ------------------------------------------------------------------

    def transform(self, chunk: pd.DataFrame) -> pd.DataFrame:
        """对原始分块做额外调整，默认原样返回。

        子类可在此实现单位换算、列重命名、数据过滤等逻辑。
        返回值必须是 pd.DataFrame，且列名须与 event_type 字段名匹配。

        Parameters
        ----------
        chunk:
            从 DataLoader 读取到的原始 DataFrame 分块。

        Returns
        -------
        pd.DataFrame
            转换后的分块，将按行构造事件实例。
        """
        return chunk

    # ------------------------------------------------------------------
    # Iterator 协议
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[DataEvent]:
        """重置迭代状态并从 loader 头部开始读取。"""
        for chunk in self._loader:
            transformed_chunk = self.transform(chunk)
            values = transformed_chunk[self._columns].to_numpy(copy=False)
            for row in values:
                yield self._event_type(*row)