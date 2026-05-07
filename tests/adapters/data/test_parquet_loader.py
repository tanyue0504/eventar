"""adapters.data.parquet_loader 模块测试。"""
from __future__ import annotations

import pandas as pd
import pytest

from eventar.adapters.data.parquet_loader import ParquetDataLoader


@pytest.fixture()
def parquet_file(tmp_path):
    """写入临时 Parquet 文件并返回路径。"""
    df = pd.DataFrame({"timestamp": [1, 2, 3, 4, 5], "value": [10, 20, 30, 40, 50]})
    p = tmp_path / "test.parquet"
    df.to_parquet(p, index=False)
    return p


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
