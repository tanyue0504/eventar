"""数据加载器抽象基类及流式 CSV / Parquet 实现。

设计要点：
- DataLoader 是一个抽象迭代器，每次 __next__ 返回一个 pd.DataFrame 分块。
- 调用方使用 for chunk in loader: 的方式流式消费数据，无需将全部数据载入内存。
- CsvDataLoader  基于 pd.read_csv chunksize 参数实现分块流读。
- ParquetDataLoader 基于 pyarrow.parquet.ParquetFile.iter_batches 实现
  按行组（row group）流读，可指定 batch_size 控制每批行数。
"""
from __future__ import annotations

from typing import Iterator
import pandas as pd

class DataLoader:
    """数据加载器抽象基类。

    实现 Iterator[pd.DataFrame] 协议：
    - __iter__ 返回自身，使加载器可直接用于 for 循环。
    - __next__ 返回下一个 DataFrame 分块；无数据时抛出 StopIteration。
    子类必须实现 __next__。
    """
    
    def __iter__(self) -> Iterator[pd.DataFrame]:
        """返回自身，使加载器可直接用于 for 循环。"""
        return self

    def __next__(self) -> pd.DataFrame:
        """返回下一个 DataFrame 分块；无数据时抛出 StopIteration。"""
        raise StopIteration

