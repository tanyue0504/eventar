"""adapters.data.csv_loader 模块测试。"""
from __future__ import annotations

import textwrap

import pandas as pd
import pytest

from eventar.adapters.data.csv_loader import CsvDataLoader

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
