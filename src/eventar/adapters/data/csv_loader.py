from eventar.data import DataLoader
from pathlib import Path
from typing import Iterator
import pandas as pd


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

    def __iter__(self) -> Iterator[pd.DataFrame]:
        yield from pd.read_csv(
            self._path,
            chunksize=self._chunksize,
            **self._read_csv_kwargs,
        )