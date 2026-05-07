"""DataEventSource 吞吐与性能分析脚本。

运行方式（在项目根目录，虚拟环境已激活）：
    python experiments/data_event_perf/source_profile.py [--rows N] [--batch-size N] [--profile]

默认跑 1000w 行，batch_size=1_000_000，仅打印吞吐。
加 --profile 时输出 cProfile 热点。
"""
from __future__ import annotations

import argparse
import cProfile
import pstats
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from eventar.adapters.data.parquet_loader import ParquetDataLoader
from eventar.adapters.data.single_source import SingleDataEventSource
from eventar.data.event import DataEvent
from eventar.data.loader import DataLoader

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "test" / "market_df_10000000.parquet"
COLUMNS = [
    "timestamp", "code", "name",
    "open", "high", "low", "close", "vol", "amount",
]


@dataclass(frozen=True, slots=True)
class MarketEvent(DataEvent):
    code: str
    name: str
    open: float
    high: float
    low: float
    close: float
    vol: int
    amount: float


def run(rows: int, batch_size: int) -> tuple[int, float, float]:
    """遍历全部数据，返回 (行数, 耗时秒, checksum)。"""
    loader = ParquetDataLoader(DATA_FILE, batch_size=batch_size, columns=COLUMNS)
    source = SingleDataEventSource(loader, COLUMNS, MarketEvent)

    if rows > 0:
        # 仅取前 N 行：用 pandas head 限制 loader
        class LimitedLoader(DataLoader):
            def __init__(self, inner, limit):
                self._inner = inner
                self._limit = limit

            def __iter__(self):
                seen = 0
                for chunk in self._inner:
                    remaining = self._limit - seen
                    if remaining <= 0:
                        return
                    if len(chunk) > remaining:
                        chunk = chunk.iloc[:remaining]
                    yield chunk
                    seen += len(chunk)

        loader = LimitedLoader(
            ParquetDataLoader(DATA_FILE, batch_size=batch_size, columns=COLUMNS), rows
        )
        # loader = ParquetDataLoader(DATA_FILE, batch_size=batch_size, columns=COLUMNS)
        source = SingleDataEventSource(loader, COLUMNS, MarketEvent)

    count = 0
    checksum = 0.0
    start = perf_counter()
    for event in source:
        count += 1
        checksum += float(event.close)
    elapsed = perf_counter() - start
    return count, elapsed, checksum


def main() -> None:
    parser = argparse.ArgumentParser(description="DataEventSource throughput & profile")
    parser.add_argument("--rows", type=int, default=-1, help="限制行数，-1 表示全部")
    parser.add_argument("--batch-size", type=int, default=1_000_000)
    parser.add_argument("--profile", action="store_true", help="输出 cProfile 报告")
    parser.add_argument("--profile-top", type=int, default=20)
    args = parser.parse_args()

    if args.profile:
        profiler = cProfile.Profile()
        profiler.enable()
        count, elapsed, checksum = run(args.rows, args.batch_size)
        profiler.disable()
    else:
        count, elapsed, checksum = run(args.rows, args.batch_size)
        profiler = None

    print(f"rows={count}")
    print(f"elapsed_seconds={elapsed:.6f}")
    print(f"rows_per_sec={count / elapsed:,.2f}")
    print(f"checksum_close={checksum:.6f}")

    if profiler is not None:
        print(f"\n=== cProfile: cumulative time (top {args.profile_top}) ===")
        pstats.Stats(profiler).strip_dirs().sort_stats("cumulative").print_stats(args.profile_top)
        print(f"\n=== cProfile: total time (top {args.profile_top}) ===")
        pstats.Stats(profiler).strip_dirs().sort_stats("tottime").print_stats(args.profile_top)


if __name__ == "__main__":
    main()
