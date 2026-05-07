from eventar.data import DataLoader
from pathlib import Path
from typing import Iterator
import pyarrow.parquet as pq
import pandas as pd

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
        for batch in pq.ParquetFile(self._path).iter_batches(
            batch_size=self._batch_size,
            columns=self._columns,
        ):
            yield batch.to_pandas()