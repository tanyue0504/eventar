"""MergedDataEventSource 测试。

覆盖场景：
- 单 source 等价于直接迭代
- 两路有序归并（各自已排序，验证合并顺序）
- 两路交错归并（交叉 timestamp）
- 同 timestamp 时按 source 索引靠前优先
- 含空 source（忽略空 source）
- 全部 source 均为空
- 可重复迭代（迭代两次结果一致）
- 局部性短路径正确性（一个 source 连续主导多轮）
- 三路归并
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import pytest

from eventar.data.source import DataEventSource
from eventar.adapters.data.merged_source import MergedDataEventSource
from eventar.data.event import DataEvent


# ---------------------------------------------------------------------------
# 辅助：最小 DataEvent 子类与 stub source
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TickEvent(DataEvent):
    """仅含 timestamp 的最小测试事件。"""


class ListSource(DataEventSource):
    """测试用：从固定 TickEvent 列表 yield 事件，不依赖文件 I/O。"""

    def __init__(self, events: list[TickEvent]) -> None:
        self._events = events

    def __iter__(self) -> Iterator[DataEvent]:
        yield from self._events


def make_ticks(*timestamps: int) -> list[TickEvent]:
    return [TickEvent(ts) for ts in timestamps]


# ---------------------------------------------------------------------------
# 单 source
# ---------------------------------------------------------------------------


def test_single_source_passthrough():
    """单 source 时，输出与原 source 完全一致。"""
    src = ListSource(make_ticks(1, 2, 3))
    merged = MergedDataEventSource([src])
    assert [e.timestamp for e in merged] == [1, 2, 3]


def test_single_source_empty():
    """单 source 为空时，输出为空。"""
    merged = MergedDataEventSource([ListSource([])])
    assert list(merged) == []


# ---------------------------------------------------------------------------
# 两路归并
# ---------------------------------------------------------------------------


def test_two_sources_sorted():
    """两路各自有序，合并结果全局有序。"""
    a = ListSource(make_ticks(1, 3, 5))
    b = ListSource(make_ticks(2, 4, 6))
    merged = MergedDataEventSource([a, b])
    assert [e.timestamp for e in merged] == [1, 2, 3, 4, 5, 6]


def test_two_sources_interleaved():
    """timestamp 完全交错，合并顺序仍正确。"""
    a = ListSource(make_ticks(1, 4, 7))
    b = ListSource(make_ticks(2, 3, 5, 6))
    merged = MergedDataEventSource([a, b])
    assert [e.timestamp for e in merged] == [1, 2, 3, 4, 5, 6, 7]


def test_two_sources_one_empty():
    """其中一路为空，另一路完整输出。"""
    a = ListSource(make_ticks(1, 2, 3))
    b = ListSource([])
    merged = MergedDataEventSource([a, b])
    assert [e.timestamp for e in merged] == [1, 2, 3]


def test_all_sources_empty():
    """全部 source 为空时，输出为空。"""
    merged = MergedDataEventSource([ListSource([]), ListSource([])])
    assert list(merged) == []


# ---------------------------------------------------------------------------
# 同 timestamp 时的索引优先级
# ---------------------------------------------------------------------------


def test_tie_breaking_by_index():
    """timestamp 相同时，索引靠前的 source 优先输出。"""

    @dataclass(frozen=True, slots=True)
    class TagEvent(DataEvent):
        tag: str

    class TagSource(DataEventSource):
        def __init__(self, events):
            self._events = events

        def __iter__(self):
            yield from self._events

    # source 0 和 source 1 都有 ts=10 的事件
    a = TagSource([TagEvent(10, "A"), TagEvent(20, "A")])
    b = TagSource([TagEvent(10, "B"), TagEvent(20, "B")])
    merged = MergedDataEventSource([a, b])
    events = list(merged)
    assert [e.tag for e in events] == ["A", "B", "A", "B"]


# ---------------------------------------------------------------------------
# 可重复迭代
# ---------------------------------------------------------------------------


def test_repeatable_iteration():
    """同一 MergedDataEventSource 可多次迭代，结果一致。"""
    a = ListSource(make_ticks(1, 3))
    b = ListSource(make_ticks(2, 4))
    merged = MergedDataEventSource([a, b])
    first = [e.timestamp for e in merged]
    second = [e.timestamp for e in merged]
    assert first == second == [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# 局部性短路径正确性
# ---------------------------------------------------------------------------


def test_locality_one_dominant_source():
    """一个 source 连续主导多轮（触发短路径），输出顺序仍然正确。"""
    # source 0 在前 5 轮全部最小，触发短路径
    a = ListSource(make_ticks(1, 2, 3, 4, 5, 100))
    b = ListSource(make_ticks(10, 20))
    merged = MergedDataEventSource([a, b])
    assert [e.timestamp for e in merged] == [1, 2, 3, 4, 5, 10, 20, 100]


def test_locality_alternating_dominance():
    """两路轮流主导，短路径频繁切换，顺序仍正确。"""
    a = ListSource(make_ticks(1, 3, 5, 7))
    b = ListSource(make_ticks(2, 4, 6, 8))
    merged = MergedDataEventSource([a, b])
    assert [e.timestamp for e in merged] == [1, 2, 3, 4, 5, 6, 7, 8]


# ---------------------------------------------------------------------------
# 三路归并
# ---------------------------------------------------------------------------


def test_three_sources():
    """三路归并，顺序正确。"""
    a = ListSource(make_ticks(1, 6))
    b = ListSource(make_ticks(2, 4))
    c = ListSource(make_ticks(3, 5))
    merged = MergedDataEventSource([a, b, c])
    assert [e.timestamp for e in merged] == [1, 2, 3, 4, 5, 6]


def test_three_sources_tie_breaking():
    """三路同 timestamp，索引最小的优先。"""

    @dataclass(frozen=True, slots=True)
    class IdEvent(DataEvent):
        sid: int

    class IdSource(DataEventSource):
        def __init__(self, sid, timestamps):
            self._events = [IdEvent(ts, sid) for ts in timestamps]

        def __iter__(self):
            yield from self._events

    merged = MergedDataEventSource([
        IdSource(0, [5]),
        IdSource(1, [5]),
        IdSource(2, [5]),
    ])
    events = list(merged)
    assert [e.sid for e in events] == [0, 1, 2]


if __name__ == "__main__":
    import pytest as _pytest

    _pytest.main([__file__, "-v"])
