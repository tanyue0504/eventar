from __future__ import annotations

import heapq
from typing import Iterator
from eventar.data import DataEvent, DataEventSource

class MergedSource(DataEventSource):
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


# backward compatibility alias
MergedDataEventSource = MergedSource