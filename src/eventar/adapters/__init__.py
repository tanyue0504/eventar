"""适配器层。

包含各种数据源、执行通道等具体实现的适配器。
"""

from eventar.adapters.data import (
	CsvDataLoader,
	MergedSource,
	ParquetDataLoader,
	SingleDataEventSource,
)

__all__ = [
	"CsvDataLoader",
	"MergedSource",
	"ParquetDataLoader",
	"SingleDataEventSource",
]
