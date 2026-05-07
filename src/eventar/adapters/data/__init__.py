"""数据适配器。

包含各种数据加载器、数据事件源等具体实现。
"""

from eventar.adapters.data.csv_loader import CsvDataLoader
from eventar.adapters.data.merged_source import MergedDataEventSource, MergedSource
from eventar.adapters.data.parquet_loader import ParquetDataLoader
from eventar.adapters.data.single_source import SingleDataEventSource
from eventar.adapters.data.timer_source import TimerSource

__all__ = [
	"CsvDataLoader",
	"MergedSource",
	"MergedDataEventSource",
	"ParquetDataLoader",
	"SingleDataEventSource",
	"TimerSource",
]
