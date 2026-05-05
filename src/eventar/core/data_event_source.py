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

import heapq
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


class MergedDataEventSource(DataEventSource):
    """多个 DataEventSource 按 timestamp 升序合并的迭代器。

    使用最小堆实现多路归并：

    - timestamp 小的优先输出。
    - timestamp 相同时，sources 列表索引小的优先（稳定性保证）。
    - 局部性短路径：若上一轮胜出的 source 下一个事件仍然最小，
      直接 yield 而不经过堆，避免不必要的 heappush/heappop 开销。

    Parameters
    ----------
    sources:
        DataEventSource 实例列表。同 timestamp 时索引靠前的优先输出。
    """

    def __init__(self, sources: list[DataEventSource]) -> None:
        # 不调用 DataEventSource.__init__，本类不使用 loader/columns/event_type。
        self._sources = sources

    def __iter__(self) -> Iterator[DataEvent]:
        iters = [iter(src) for src in self._sources]
        # 堆元素：(timestamp, source_index, event)
        # source_index 保证同 timestamp 时不会比较 event 对象（DataEvent 不支持排序）。
        heap: list[tuple] = []

        # 初始化：从每个 source 取首个事件入堆。
        for i, it in enumerate(iters):
            try:
                ev = next(it)
                heapq.heappush(heap, (ev.timestamp, i, ev))
            except StopIteration:
                pass

        while heap:
            _, i, ev = heapq.heappop(heap)
            yield ev

            # 局部性短路径：持续从 source i 消费，直到它不再是最小值。
            # 避免对同一 source 连续执行 heappush + heappop，减少堆操作。
            while True:
                try:
                    nev = next(iters[i])
                except StopIteration:
                    break  # source i 已耗尽，退出内层循环

                heap_ts = heap[0][0] if heap else None
                heap_i = heap[0][1] if heap else None

                # 短路条件：堆为空，或 nev 严格更小，或同 timestamp 但索引更小。
                if (
                    heap_ts is None
                    or nev.timestamp < heap_ts
                    or (nev.timestamp == heap_ts and i < heap_i)
                ):
                    yield nev
                    # 继续内层循环，保持在 source i 上。
                else:
                    # source i 不再是最小值，将 nev 入堆后回到外层循环。
                    heapq.heappush(heap, (nev.timestamp, i, nev))
                    break