from __future__ import annotations

import argparse
from dataclasses import dataclass
from itertools import starmap
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, Iterator, Sequence

import pandas as pd
import pyperf
import numpy as np


DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "test" / "market_df_10000000.parquet"
FIELD_NAMES = (
    "timestamp",
    "code",
    "name",
    "open",
    "high",
    "low",
    "close",
    "vol",
    "amount",
)
FIELD_INDEX = {name: index for index, name in enumerate(FIELD_NAMES)}


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


@dataclass(slots=True)
class EventHeader:
    timestamp: pd.Timestamp
    code: str


@dataclass(slots=True)
class PayloadTupleEvent:
    header: EventHeader
    payload: tuple[object, ...]

    @property
    def timestamp(self) -> pd.Timestamp:
        return self.header.timestamp

    @property
    def code(self) -> str:
        return self.header.code

    @property
    def name(self) -> str:
        return self.payload[FIELD_INDEX["name"]]

    @property
    def open(self) -> float:
        return self.payload[FIELD_INDEX["open"]]

    @property
    def high(self) -> float:
        return self.payload[FIELD_INDEX["high"]]

    @property
    def low(self) -> float:
        return self.payload[FIELD_INDEX["low"]]

    @property
    def close(self) -> float:
        return self.payload[FIELD_INDEX["close"]]

    @property
    def vol(self) -> int:
        return self.payload[FIELD_INDEX["vol"]]

    @property
    def amount(self) -> float:
        return self.payload[FIELD_INDEX["amount"]]


@dataclass(slots=True)
class PayloadObjectEvent:
    header: EventHeader
    payload: object

    @property
    def timestamp(self) -> pd.Timestamp:
        return self.header.timestamp

    @property
    def code(self) -> str:
        return self.header.code

    @property
    def name(self) -> str:
        return getattr(self.payload, "name")

    @property
    def open(self) -> float:
        return getattr(self.payload, "open")

    @property
    def high(self) -> float:
        return getattr(self.payload, "high")

    @property
    def low(self) -> float:
        return getattr(self.payload, "low")

    @property
    def close(self) -> float:
        return getattr(self.payload, "close")

    @property
    def vol(self) -> int:
        return getattr(self.payload, "vol")

    @property
    def amount(self) -> float:
        return getattr(self.payload, "amount")


@dataclass(slots=True)
class ColumnarEventView:
    columns: dict[str, Sequence[object]]
    row_index: int = 0

    def bind(self, row_index: int) -> None:
        self.row_index = row_index

    @property
    def timestamp(self) -> pd.Timestamp:
        return self.columns["timestamp"][self.row_index]

    @property
    def code(self) -> str:
        return self.columns["code"][self.row_index]

    @property
    def name(self) -> str:
        return self.columns["name"][self.row_index]

    @property
    def open(self) -> float:
        return self.columns["open"][self.row_index]

    @property
    def high(self) -> float:
        return self.columns["high"][self.row_index]

    @property
    def low(self) -> float:
        return self.columns["low"][self.row_index]

    @property
    def close(self) -> float:
        return self.columns["close"][self.row_index]

    @property
    def vol(self) -> int:
        return self.columns["vol"][self.row_index]

    @property
    def amount(self) -> float:
        return self.columns["amount"][self.row_index]


def load_frame(rows: int) -> pd.DataFrame:
    frame = pd.read_parquet(DATA_FILE, engine="pyarrow", columns=list(FIELD_NAMES))
    if rows > 0:
        return frame.head(rows).copy()
    return frame


def build_columns(frame: pd.DataFrame) -> dict[str, Sequence[object]]:
    return {name: frame[name].to_numpy(copy=False) for name in FIELD_NAMES}


def iter_zip_columns(columns: dict[str, Sequence[object]]) -> Iterator[tuple[object, ...]]:
    return zip(*(columns[name] for name in FIELD_NAMES))


def iter_values(frame: pd.DataFrame) -> Iterator[Sequence[object]]:
    return iter(frame.to_numpy(copy=False))


def iter_itertuples_named(frame: pd.DataFrame) -> Iterator[object]:
    return frame.itertuples(index=False, name="MarketRow")


def iter_itertuples_plain(frame: pd.DataFrame) -> Iterator[tuple[object, ...]]:
    return frame.itertuples(index=False, name=None)


def iter_iterrows(frame: pd.DataFrame) -> Iterator[pd.Series]:
    for _, row in frame.iterrows():
        yield row


def access_event(event: object) -> float:
    checksum = float(timestamp_ns(getattr(event, "timestamp")) % 997)
    checksum += float(getattr(event, "open"))
    checksum += float(getattr(event, "high"))
    checksum -= float(getattr(event, "low"))
    checksum += float(getattr(event, "close"))
    checksum += float(getattr(event, "amount")) / max(int(getattr(event, "vol")), 1)
    checksum += float(len(getattr(event, "code")))
    checksum += float(len(getattr(event, "name")))
    return checksum


def access_tuple_row(row: Sequence[object]) -> float:
    checksum = float(timestamp_ns(row[FIELD_INDEX["timestamp"]]) % 997)
    checksum += float(row[FIELD_INDEX["open"]])
    checksum += float(row[FIELD_INDEX["high"]])
    checksum -= float(row[FIELD_INDEX["low"]])
    checksum += float(row[FIELD_INDEX["close"]])
    checksum += float(row[FIELD_INDEX["amount"]]) / max(int(row[FIELD_INDEX["vol"]]), 1)
    checksum += float(len(row[FIELD_INDEX["code"]]))
    checksum += float(len(row[FIELD_INDEX["name"]]))
    return checksum


def access_named_row(row: object) -> float:
    checksum = float(timestamp_ns(row.timestamp) % 997)
    checksum += float(row.open)
    checksum += float(row.high)
    checksum -= float(row.low)
    checksum += float(row.close)
    checksum += float(row.amount) / max(int(row.vol), 1)
    checksum += float(len(row.code))
    checksum += float(len(row.name))
    return checksum


def access_series_row(row: pd.Series) -> float:
    checksum = float(timestamp_ns(row["timestamp"]) % 997)
    checksum += float(row["open"])
    checksum += float(row["high"])
    checksum -= float(row["low"])
    checksum += float(row["close"])
    checksum += float(row["amount"]) / max(int(row["vol"]), 1)
    checksum += float(len(row["code"]))
    checksum += float(len(row["name"]))
    return checksum


def timestamp_ns(value: object) -> int:
    if isinstance(value, pd.Timestamp):
        return int(value.value)
    if isinstance(value, np.datetime64):
        return int(value.astype("datetime64[ns]").astype(np.int64))
    return int(pd.Timestamp(value).value)


def consume_iterable(rows: Iterable[object], accessor) -> float:
    checksum = 0.0
    for row in rows:
        checksum += accessor(row)
    return checksum


def benchmark_iteration_zip(columns: dict[str, Sequence[object]]) -> float:
    return consume_iterable(iter_zip_columns(columns), access_tuple_row)


def benchmark_iteration_values(frame: pd.DataFrame) -> float:
    return consume_iterable(iter_values(frame), access_tuple_row)


def benchmark_iteration_itertuples_named(frame: pd.DataFrame) -> float:
    return consume_iterable(iter_itertuples_named(frame), access_named_row)


def benchmark_iteration_itertuples_plain(frame: pd.DataFrame) -> float:
    return consume_iterable(iter_itertuples_plain(frame), access_tuple_row)


def benchmark_iteration_iterrows(frame: pd.DataFrame) -> float:
    return consume_iterable(iter_iterrows(frame), access_series_row)


def benchmark_construction_flat_append(columns: dict[str, Sequence[object]]) -> float:
    checksum = 0.0
    for row in iter_zip_columns(columns):
        event = FlatMarketEvent(*row)
        checksum += access_event(event)
    return checksum


def benchmark_construction_flat_starmap(columns: dict[str, Sequence[object]]) -> float:
    checksum = 0.0
    for event in starmap(FlatMarketEvent, iter_zip_columns(columns)):
        checksum += access_event(event)
    return checksum


def benchmark_construction_payload_tuple(columns: dict[str, Sequence[object]]) -> float:
    checksum = 0.0
    for row in iter_zip_columns(columns):
        event = PayloadTupleEvent(header=EventHeader(timestamp=row[0], code=row[1]), payload=row)
        checksum += access_event(event)
    return checksum


def benchmark_construction_columnar_view(columns: dict[str, Sequence[object]]) -> float:
    checksum = 0.0
    event = ColumnarEventView(columns)
    for row_index in range(len(columns["timestamp"])):
        event.bind(row_index)
        checksum += access_event(event)
    return checksum


def benchmark_event_shape_flat(columns: dict[str, Sequence[object]]) -> float:
    checksum = 0.0
    for row in iter_zip_columns(columns):
        checksum += access_event(FlatMarketEvent(*row))
    return checksum


def benchmark_event_shape_tuple_payload(columns: dict[str, Sequence[object]]) -> float:
    checksum = 0.0
    for row in iter_zip_columns(columns):
        checksum += access_event(PayloadTupleEvent(EventHeader(row[0], row[1]), row))
    return checksum


def benchmark_event_shape_object_payload(columns: dict[str, Sequence[object]]) -> float:
    checksum = 0.0
    for row in iter_itertuples_named(pd.DataFrame(columns)):
        event = PayloadObjectEvent(
            header=EventHeader(timestamp=row.timestamp, code=row.code),
            payload=SimpleNamespace(
                name=row.name,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                vol=row.vol,
                amount=row.amount,
            ),
        )
        checksum += access_event(event)
    return checksum


def benchmark_event_shape_columnar_view(columns: dict[str, Sequence[object]]) -> float:
    return benchmark_construction_columnar_view(columns)


def register_iteration_benchmarks(runner: pyperf.Runner, frame: pd.DataFrame) -> None:
    columns = build_columns(frame)
    runner.bench_func("iteration/zip-columns", benchmark_iteration_zip, columns)
    runner.bench_func("iteration/values", benchmark_iteration_values, frame)
    runner.bench_func("iteration/itertuples-named", benchmark_iteration_itertuples_named, frame)
    runner.bench_func("iteration/itertuples-plain", benchmark_iteration_itertuples_plain, frame)
    runner.bench_func("iteration/iterrows", benchmark_iteration_iterrows, frame)


def register_construction_benchmarks(runner: pyperf.Runner, frame: pd.DataFrame) -> None:
    columns = build_columns(frame)
    runner.bench_func("construction/flat-append", benchmark_construction_flat_append, columns)
    runner.bench_func("construction/flat-starmap", benchmark_construction_flat_starmap, columns)
    runner.bench_func("construction/payload-tuple", benchmark_construction_payload_tuple, columns)
    runner.bench_func("construction/columnar-view", benchmark_construction_columnar_view, columns)


def register_event_shape_benchmarks(runner: pyperf.Runner, frame: pd.DataFrame) -> None:
    columns = build_columns(frame)
    runner.bench_func("event-shape/flat", benchmark_event_shape_flat, columns)
    runner.bench_func("event-shape/payload-tuple", benchmark_event_shape_tuple_payload, columns)
    runner.bench_func("event-shape/payload-object", benchmark_event_shape_object_payload, columns)
    runner.bench_func("event-shape/columnar-view", benchmark_event_shape_columnar_view, columns)


def create_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark data-to-event conversion strategies")
    parser.add_argument(
        "--group",
        choices=("all", "iteration", "construction", "event-shape"),
        default="all",
        help="Select a benchmark group",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=200_000,
        help="Number of rows loaded from the parquet dataset",
    )
    return parser


def add_worker_args(cmd: list[str], args: argparse.Namespace) -> None:
    cmd.extend(["--group", args.group, "--rows", str(args.rows)])


def main() -> None:
    runner = pyperf.Runner(_argparser=create_argparser(), add_cmdline_args=add_worker_args)
    args = runner.parse_args()
    frame = load_frame(args.rows)
    runner.metadata["rows"] = len(frame)
    runner.metadata["data_file"] = str(DATA_FILE)

    if args.group in {"all", "iteration"}:
        register_iteration_benchmarks(runner, frame)
    if args.group in {"all", "construction"}:
        register_construction_benchmarks(runner, frame)
    if args.group in {"all", "event-shape"}:
        register_event_shape_benchmarks(runner, frame)


if __name__ == "__main__":
    main()