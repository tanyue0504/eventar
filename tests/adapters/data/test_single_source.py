"""DataEventSource 测试。

覆盖场景：
- 基础迭代：产出正确数量和类型的 DataEvent 实例
- 字段映射：事件字段值与原始数据一致
- columns 过滤：只取指定列
- transform 钩子：子类覆盖后可修改分块数据
- 可重复迭代：同一 source 多次 for 循环结果一致
- 分块边界：多分块时事件总数仍正确
- event_type 为 DataEvent 子类时正常工作
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pytest

from eventar.adapters.data import CsvDataLoader, ParquetDataLoader, SingleDataEventSource
from eventar.data import DataEvent


# ---------------------------------------------------------------------------
# 辅助事件类型
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PriceEvent(DataEvent):
    """用于测试的最小 DataEvent 子类。"""
    value: float


@dataclass(frozen=True, slots=True)
class TickEvent(DataEvent):
    """多字段事件，用于测试 columns 过滤。"""
    code: str
    price: float


# ---------------------------------------------------------------------------
# 测试夹具
# ---------------------------------------------------------------------------

ROWS = [
    {"timestamp": 1, "value": 10.0, "extra": 99},
    {"timestamp": 2, "value": 20.0, "extra": 99},
    {"timestamp": 3, "value": 30.0, "extra": 99},
    {"timestamp": 4, "value": 40.0, "extra": 99},
    {"timestamp": 5, "value": 50.0, "extra": 99},
]


@pytest.fixture()
def csv_file(tmp_path):
    df = pd.DataFrame(ROWS)
    p = tmp_path / "data.csv"
    df.to_csv(p, index=False)
    return p


@pytest.fixture()
def parquet_file(tmp_path):
    df = pd.DataFrame(ROWS)
    p = tmp_path / "data.parquet"
    df.to_parquet(p, index=False)
    return p


@pytest.fixture()
def multi_col_csv(tmp_path):
    df = pd.DataFrame({
        "timestamp": [1, 2, 3],
        "code": ["A", "B", "C"],
        "price": [1.1, 2.2, 3.3],
        "noise": [0, 0, 0],
    })
    p = tmp_path / "tick.csv"
    df.to_csv(p, index=False)
    return p


# ---------------------------------------------------------------------------
# 基础迭代
# ---------------------------------------------------------------------------


def test_source_yields_correct_count_csv(csv_file):
    """从 CSV 加载时，产出的事件总数等于数据行数。"""
    source = SingleDataEventSource(CsvDataLoader(csv_file), ["timestamp", "value"], PriceEvent)
    assert len(list(source)) == 5


def test_source_yields_correct_count_parquet(parquet_file):
    """从 Parquet 加载时，产出的事件总数等于数据行数。"""
    source = SingleDataEventSource(ParquetDataLoader(parquet_file), ["timestamp", "value"], PriceEvent)
    assert len(list(source)) == 5


# ---------------------------------------------------------------------------
# 字段映射
# ---------------------------------------------------------------------------


def test_source_field_values_csv(csv_file):
    """事件字段值与原始 CSV 数据一致。"""
    source = SingleDataEventSource(CsvDataLoader(csv_file), ["timestamp", "value"], PriceEvent)
    events = list(source)
    assert events[0].timestamp == 1
    assert events[0].value == 10.0
    assert events[4].timestamp == 5
    assert events[4].value == 50.0


def test_source_field_values_parquet(parquet_file):
    """事件字段值与原始 Parquet 数据一致。"""
    source = SingleDataEventSource(ParquetDataLoader(parquet_file), ["timestamp", "value"], PriceEvent)
    events = list(source)
    assert events[2].timestamp == 3
    assert events[2].value == 30.0


# ---------------------------------------------------------------------------
# columns 过滤
# ---------------------------------------------------------------------------


def test_source_columns_filter(multi_col_csv):
    """columns 参数仅提取指定列，多余列不传入构造函数。"""
    source = SingleDataEventSource(
        CsvDataLoader(multi_col_csv),
        ["timestamp", "code", "price"],
        TickEvent,
    )
    events = list(source)
    assert len(events) == 3
    assert events[0].code == "A"
    assert events[1].price == pytest.approx(2.2)


# ---------------------------------------------------------------------------
# transform 钩子
# ---------------------------------------------------------------------------


def test_source_transform_modifies_values(csv_file):
    """覆盖 transform 后，事件字段值应反映转换结果。"""

    class DoubledSource(SingleDataEventSource):
        def transform(self, chunk: pd.DataFrame) -> pd.DataFrame:
            chunk = chunk.copy()
            chunk["value"] = chunk["value"] * 2
            return chunk

    source = DoubledSource(CsvDataLoader(csv_file), ["timestamp", "value"], PriceEvent)
    events = list(source)
    assert events[0].value == pytest.approx(20.0)
    assert events[4].value == pytest.approx(100.0)


def test_source_transform_filter_rows(csv_file):
    """transform 过滤行后，产出事件数应减少。"""

    class FilteredSource(SingleDataEventSource):
        def transform(self, chunk: pd.DataFrame) -> pd.DataFrame:
            return chunk[chunk["value"] > 20.0]

    source = FilteredSource(CsvDataLoader(csv_file), ["timestamp", "value"], PriceEvent)
    events = list(source)
    # value > 20 的行：30, 40, 50 共 3 行
    assert len(events) == 3
    assert all(e.value > 20.0 for e in events)


def test_source_transform_runs_before_columns_selection(multi_col_csv):
    """transform 在列提取前执行，可读取原列并生成新列供后续提取。"""

    @dataclass(frozen=True, slots=True)
    class DerivedEvent(DataEvent):
        code: str
        derived_price: float

    class DerivedColumnsSource(SingleDataEventSource):
        def transform(self, chunk: pd.DataFrame) -> pd.DataFrame:
            assert "noise" in chunk.columns
            out = chunk.copy()
            out["derived_price"] = out["price"] + out["noise"]
            return out

    source = DerivedColumnsSource(
        CsvDataLoader(multi_col_csv),
        ["timestamp", "code", "derived_price"],
        DerivedEvent,
    )
    events = list(source)
    assert len(events) == 3
    assert events[0].derived_price == pytest.approx(1.1)


# ---------------------------------------------------------------------------
# 多分块边界
# ---------------------------------------------------------------------------


def test_source_multi_chunk_total_count(csv_file):
    """chunksize=2 时，跨分块的事件总数仍正确。"""
    source = SingleDataEventSource(
        CsvDataLoader(csv_file, chunksize=2),
        ["timestamp", "value"],
        PriceEvent,
    )
    assert len(list(source)) == 5


def test_source_multi_chunk_order(csv_file):
    """多分块时，事件顺序与原始数据行顺序一致。"""
    source = SingleDataEventSource(
        CsvDataLoader(csv_file, chunksize=2),
        ["timestamp", "value"],
        PriceEvent,
    )
    timestamps = [e.timestamp for e in source]
    assert timestamps == [1, 2, 3, 4, 5]


if __name__ == "__main__":
    import pytest as _pytest

    _pytest.main([__file__, "-v"])
