"""data_loader 模块测试。

覆盖场景：
- DataLoader 可迭代契约（行为导向，不约束必须实现 __next__）
- CsvDataLoader：分块迭代、全量收集、可重复迭代、透传 kwargs
- ParquetDataLoader：分块迭代、全量收集、可重复迭代、columns 过滤
"""
from __future__ import annotations

import io
import textwrap

import pandas as pd
import pytest

from eventar.core.data_loader import CsvDataLoader, DataLoader, ParquetDataLoader


# ---------------------------------------------------------------------------
# 测试夹具
# ---------------------------------------------------------------------------

CSV_CONTENT = textwrap.dedent("""\
    timestamp,value
    1,10
    2,20
    3,30
    4,40
    5,50
""")


@pytest.fixture()
def csv_file(tmp_path):
    """写入临时 CSV 文件并返回路径。"""
    p = tmp_path / "test.csv"
    p.write_text(CSV_CONTENT, encoding="utf-8")
    return p


@pytest.fixture()
def parquet_file(tmp_path):
    """写入临时 Parquet 文件并返回路径。"""
    df = pd.DataFrame({"timestamp": [1, 2, 3, 4, 5], "value": [10, 20, 30, 40, 50]})
    p = tmp_path / "test.parquet"
    df.to_parquet(p, index=False)
    return p


# ---------------------------------------------------------------------------
# DataLoader 可迭代契约
# ---------------------------------------------------------------------------


def test_data_loader_generator_subclass_iterable():
    """只实现生成器式 __iter__ 的子类也应可正常迭代。"""

    class SingleChunk(DataLoader):
        def __iter__(self):
            yield pd.DataFrame({"x": [1, 2, 3]})

    loader = SingleChunk()
    chunks = list(loader)
    assert len(chunks) == 1
    assert list(chunks[0]["x"]) == [1, 2, 3]


# ---------------------------------------------------------------------------
# CsvDataLoader
# ---------------------------------------------------------------------------


def test_csv_loader_all_rows(csv_file):
    """所有分块合并后行数等于原始 CSV 行数。"""
    loader = CsvDataLoader(csv_file, chunksize=10_000)
    result = pd.concat(list(loader), ignore_index=True)
    assert len(result) == 5


def test_csv_loader_chunking(csv_file):
    """chunksize=2 时应产生 3 个分块（2+2+1）。"""
    loader = CsvDataLoader(csv_file, chunksize=2)
    chunks = list(loader)
    assert len(chunks) == 3
    assert len(chunks[0]) == 2
    assert len(chunks[1]) == 2
    assert len(chunks[2]) == 1


def test_csv_loader_chunk_is_dataframe(csv_file):
    """每个分块必须是 pd.DataFrame。"""
    loader = CsvDataLoader(csv_file, chunksize=2)
    for chunk in loader:
        assert isinstance(chunk, pd.DataFrame)


def test_csv_loader_repeatable(csv_file):
    """同一加载器可多次迭代，每次均返回完整数据。"""
    loader = CsvDataLoader(csv_file, chunksize=2)
    first = pd.concat(list(loader), ignore_index=True)
    second = pd.concat(list(loader), ignore_index=True)
    pd.testing.assert_frame_equal(first, second)


def test_csv_loader_passthrough_kwargs(csv_file):
    """dtype 等 kwargs 正确透传给 pd.read_csv。"""
    loader = CsvDataLoader(csv_file, chunksize=10_000, dtype={"value": float})
    chunk = next(iter(loader))
    assert chunk["value"].dtype == float


# ---------------------------------------------------------------------------
# ParquetDataLoader
# ---------------------------------------------------------------------------


def test_parquet_loader_all_rows(parquet_file):
    """所有分块合并后行数等于原始 Parquet 行数。"""
    loader = ParquetDataLoader(parquet_file, batch_size=10_000)
    result = pd.concat(list(loader), ignore_index=True)
    assert len(result) == 5


def test_parquet_loader_chunking(parquet_file):
    """batch_size=2 时应产生至少 3 个分块。"""
    loader = ParquetDataLoader(parquet_file, batch_size=2)
    chunks = list(loader)
    total = sum(len(c) for c in chunks)
    assert total == 5


def test_parquet_loader_chunk_is_dataframe(parquet_file):
    """每个分块必须是 pd.DataFrame。"""
    loader = ParquetDataLoader(parquet_file, batch_size=2)
    for chunk in loader:
        assert isinstance(chunk, pd.DataFrame)


def test_parquet_loader_repeatable(parquet_file):
    """同一加载器可多次迭代，每次均返回完整数据。"""
    loader = ParquetDataLoader(parquet_file, batch_size=2)
    first = pd.concat(list(loader), ignore_index=True)
    second = pd.concat(list(loader), ignore_index=True)
    pd.testing.assert_frame_equal(first, second)


def test_parquet_loader_columns(parquet_file):
    """columns 参数仅加载指定列。"""
    loader = ParquetDataLoader(parquet_file, batch_size=10_000, columns=["value"])
    chunk = next(iter(loader))
    assert list(chunk.columns) == ["value"]


if __name__ == "__main__":
    import pytest as _pytest

    _pytest.main([__file__, "-v"])
