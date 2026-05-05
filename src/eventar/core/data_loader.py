"""数据加载器抽象基类及流式 CSV / Parquet 实现。

设计要点：
- DataLoader 是一个抽象迭代器，每次 __next__ 返回一个 pd.DataFrame 分块。
- 调用方使用 for chunk in loader: 的方式流式消费数据，无需将全部数据载入内存。
- CsvDataLoader  基于 pd.read_csv chunksize 参数实现分块流读。
- ParquetDataLoader 基于 pyarrow.parquet.ParquetFile.iter_batches 实现
  按行组（row group）流读，可指定 batch_size 控制每批行数。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator
import pyarrow.parquet as pq
import pandas as pd


class DataLoader(ABC):
    """数据加载器抽象基类。

    实现 Iterator[pd.DataFrame] 协议：
    - __iter__ 返回自身，使加载器可直接用于 for 循环。
    - __next__ 返回下一个 DataFrame 分块；无数据时抛出 StopIteration。
    子类必须实现 __next__。
    """

    def __iter__(self) -> Iterator[pd.DataFrame]:
        return self

    @abstractmethod
    def __next__(self) -> pd.DataFrame:
        """返回下一个 DataFrame 分块。无更多数据时抛出 StopIteration。"""

    def close(self) -> None:
        """释放底层资源。子类可覆盖。"""


class CsvDataLoader(DataLoader):
    """流式 CSV 加载器。

    使用 pd.read_csv 的 chunksize 参数按块读取，适合大文件场景。

    Parameters
    ----------
    path:
        CSV 文件路径。
    chunksize:
        每块包含的最大行数，默认 1 000 000。
    **read_csv_kwargs:
        透传给 pd.read_csv 的其他关键字参数（如 dtype、parse_dates 等）。
    """

    def __init__(
        self,
        path: str | Path,
        chunksize: int = 1_000_000,
        **read_csv_kwargs,
    ) -> None:
        self._path = Path(path)
        self._chunksize = chunksize
        self._read_csv_kwargs = read_csv_kwargs
        self._reader: pd.io.parsers.readers.TextFileReader | None = None

    def __iter__(self) -> Iterator[pd.DataFrame]:
        # 每次迭代重新打开文件，确保可重复使用
        self.close()
        self._reader = pd.read_csv(
            self._path,
            chunksize=self._chunksize,
            **self._read_csv_kwargs,
        )
        return self

    def __next__(self) -> pd.DataFrame:
        if self._reader is None:
            raise StopIteration
        try:
            return next(self._reader)
        except StopIteration:
            self.close()
            raise

    def close(self) -> None:
        """关闭底层文件句柄。"""
        if self._reader is not None:
            self._reader.close()
            self._reader = None


class ParquetDataLoader(DataLoader):
    """流式 Parquet 加载器。

    使用 pyarrow.parquet.ParquetFile.iter_batches 按批次读取，
    每批次转为 pd.DataFrame 返回，适合列式大文件场景。

    Parameters
    ----------
    path:
        Parquet 文件路径。
    batch_size:
        每批次包含的最大行数，默认 1 000 000。
    columns:
        仅读取指定列（列名列表）；为 None 时读取全部列。
    """

    def __init__(
        self,
        path: str | Path,
        batch_size: int = 1_000_000,
        columns: list[str] | None = None,
    ) -> None:
        self._path = Path(path)
        self._batch_size = batch_size
        self._columns = columns
        self._file = None
        self._batches = None

    def __iter__(self) -> Iterator[pd.DataFrame]:
        self.close()
        self._file = pq.ParquetFile(self._path)
        self._batches = self._file.iter_batches(
            batch_size=self._batch_size,
            columns=self._columns,
        )
        return self

    def __next__(self) -> pd.DataFrame:
        if self._batches is None:
            raise StopIteration
        try:
            batch = next(self._batches)
            return batch.to_pandas()
        except StopIteration:
            self.close()
            raise

    def close(self) -> None:
        """关闭底层 Parquet 文件句柄。"""
        self._batches = None
        if self._file is not None:
            self._file = None
