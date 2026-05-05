from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import pandas as pd


DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "test" / "market_df_10000000.parquet"
FIELDS = [
    "timestamp",
    "code",
    "name",
    "open",
    "high",
    "low",
    "close",
    "vol",
    "amount",
]


@dataclass(slots=True)
class FlatMarketEvent:
    timestamp: pd.Timestamp
    code: str
    name: str
    open: float
    high: float
    low: float
    close: float
    vol: int
    amount: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Time best-path DataFrame iteration and event construction on market data"
    )
    parser.add_argument(
        "--data-file",
        type=Path,
        default=DATA_FILE,
        help="Parquet data file path",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=10_000_000,
        help="Rows to process, -1 means all rows",
    )
    return parser.parse_args()


def as_seconds(value: float) -> str:
    return f"{value:.6f}s"


def checksum_row(row: tuple[object, ...]) -> float:
    ts = row[0]
    ns = int(ts.value if hasattr(ts, "value") else pd.Timestamp(ts).value)
    return (
        float(ns % 997)
        + float(row[3])
        + float(row[4])
        - float(row[5])
        + float(row[6])
        + float(row[8]) / max(int(row[7]), 1)
        + float(len(row[1]))
        + float(len(row[2]))
    )


def checksum_event(event: FlatMarketEvent) -> float:
    return (
        float(event.timestamp.value % 997)
        + float(event.open)
        + float(event.high)
        - float(event.low)
        + float(event.close)
        + float(event.amount) / max(int(event.vol), 1)
        + float(len(event.code))
        + float(len(event.name))
    )


def main() -> None:
    args = parse_args()

    print(f"data_file={args.data_file}")
    print(f"rows_target={args.rows}")

    t0 = perf_counter()
    frame = pd.read_parquet(args.data_file, engine="pyarrow", columns=FIELDS)
    if args.rows >= 0:
        frame = frame.head(args.rows).copy()
    t_load = perf_counter() - t0

    row_count = len(frame)
    print(f"rows_loaded={row_count}")

    t1 = perf_counter()
    values = frame.to_numpy(copy=False)
    t_values = perf_counter() - t1

    # 1) Pure iteration + direct row access.
    t2 = perf_counter()
    checksum_iter_only = 0.0
    for row in values:
        checksum_iter_only += checksum_row(row)
    t_iter_only = perf_counter() - t2

    # 2) Iteration + event construction only.
    t3 = perf_counter()
    checksum_construct_only = 0.0
    for row in values:
        event = FlatMarketEvent(*row)
        checksum_construct_only += float(event.close)
    t_construct_only = perf_counter() - t3

    # 3) Iteration + event construction + attribute access.
    t4 = perf_counter()
    checksum_full = 0.0
    for row in values:
        event = FlatMarketEvent(*row)
        checksum_full += checksum_event(event)
    t_full = perf_counter() - t4

    t_total = t_load + t_values + t_full

    print("\n=== Timing Summary ===")
    print(f"load_parquet={as_seconds(t_load)}")
    print(f"to_numpy_view={as_seconds(t_values)}")
    print(f"iterate_direct_row={as_seconds(t_iter_only)}")
    print(f"iterate_construct_event={as_seconds(t_construct_only)}")
    print(f"iterate_construct_and_access={as_seconds(t_full)}")
    print(f"total(load+view+full_loop)={as_seconds(t_total)}")

    print("\n=== Throughput ===")
    print(f"rows_per_sec_direct={row_count / t_iter_only:,.2f}")
    print(f"rows_per_sec_construct={row_count / t_construct_only:,.2f}")
    print(f"rows_per_sec_full={row_count / t_full:,.2f}")

    print("\n=== Checksums ===")
    print(f"checksum_iter_only={checksum_iter_only:.6f}")
    print(f"checksum_construct_only={checksum_construct_only:.6f}")
    print(f"checksum_full={checksum_full:.6f}")


if __name__ == "__main__":
    main()
