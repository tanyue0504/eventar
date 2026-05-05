from __future__ import annotations

import argparse
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Iterator

import numpy as np
import pyarrow.parquet as pq


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


@dataclass
class PipelineStats:
    name: str
    rows: int
    batches: int
    fetch_seconds: float
    consume_seconds: float
    total_seconds: float
    checksum: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare plain streaming vs prefetch-thread streaming on heavy consumers"
    )
    parser.add_argument("--data-file", type=Path, default=DATA_FILE, help="Parquet data file")
    parser.add_argument("--batch-rows", type=int, default=200_000, help="Rows per streamed batch")
    parser.add_argument(
        "--max-batches",
        type=int,
        default=-1,
        help="Limit consumed batches; -1 means consume all",
    )
    parser.add_argument(
        "--prefetch-size",
        type=int,
        default=3,
        help="Queue size used by prefetch loader",
    )
    parser.add_argument(
        "--consumer-mode",
        choices=["cpu", "sleep", "mixed"],
        default="mixed",
        help="Heavy consumer simulation mode",
    )
    parser.add_argument(
        "--sleep-ms",
        type=float,
        default=8.0,
        help="Per-batch sleep for sleep/mixed mode",
    )
    parser.add_argument(
        "--cpu-repeats",
        type=int,
        default=2,
        help="How many extra vectorized compute rounds run per batch",
    )
    return parser.parse_args()


def iter_parquet_batches(
    data_file: Path,
    batch_rows: int,
    max_batches: int,
) -> Iterator[dict[str, np.ndarray]]:
    parquet_file = pq.ParquetFile(data_file)
    produced = 0
    for record_batch in parquet_file.iter_batches(batch_size=batch_rows, columns=FIELDS, use_threads=True):
        batch = {
            "timestamp": record_batch.column(0).to_numpy(zero_copy_only=False),
            "code": record_batch.column(1).to_numpy(zero_copy_only=False),
            "name": record_batch.column(2).to_numpy(zero_copy_only=False),
            "open": record_batch.column(3).to_numpy(zero_copy_only=False),
            "high": record_batch.column(4).to_numpy(zero_copy_only=False),
            "low": record_batch.column(5).to_numpy(zero_copy_only=False),
            "close": record_batch.column(6).to_numpy(zero_copy_only=False),
            "vol": record_batch.column(7).to_numpy(zero_copy_only=False),
            "amount": record_batch.column(8).to_numpy(zero_copy_only=False),
        }
        yield batch
        produced += 1
        if max_batches > 0 and produced >= max_batches:
            return


def iter_prefetch_batches(
    data_file: Path,
    batch_rows: int,
    max_batches: int,
    prefetch_size: int,
) -> Iterator[dict[str, np.ndarray]]:
    out_queue: queue.Queue[object] = queue.Queue(maxsize=max(prefetch_size, 1))
    done = object()
    error_box: list[BaseException] = []

    def producer() -> None:
        try:
            for batch in iter_parquet_batches(data_file, batch_rows, max_batches):
                out_queue.put(batch)
        except BaseException as exc:  # noqa: BLE001
            error_box.append(exc)
        finally:
            out_queue.put(done)

    thread = threading.Thread(target=producer, name="parquet-prefetch", daemon=True)
    thread.start()

    while True:
        item = out_queue.get()
        if item is done:
            break
        yield item  # type: ignore[misc]

    thread.join()
    if error_box:
        raise RuntimeError("prefetch producer failed") from error_box[0]


def heavy_consume(
    batch: dict[str, np.ndarray],
    mode: str,
    sleep_ms: float,
    cpu_repeats: int,
) -> float:
    # Compute a realistic per-batch factor using several numeric fields.
    base = (
        batch["open"].astype(np.float64)
        + batch["high"].astype(np.float64)
        - batch["low"].astype(np.float64)
        + batch["close"].astype(np.float64)
        + batch["amount"].astype(np.float64) / np.maximum(batch["vol"].astype(np.float64), 1.0)
    )
    score = float(base.sum())

    if mode in {"cpu", "mixed"}:
        work = base
        for _ in range(max(cpu_repeats, 0)):
            work = np.sqrt(work * 1.00001 + 3.0) + np.log1p(work)
        score += float(work.sum())

    if mode in {"sleep", "mixed"} and sleep_ms > 0:
        time.sleep(sleep_ms / 1000.0)

    score += float(batch["timestamp"].shape[0])
    score += float(len(batch["code"][0])) if batch["code"].size else 0.0
    return score


def run_pipeline(
    name: str,
    batch_iter: Iterator[dict[str, np.ndarray]],
    mode: str,
    sleep_ms: float,
    cpu_repeats: int,
) -> PipelineStats:
    rows = 0
    batches = 0
    checksum = 0.0
    fetch_seconds = 0.0
    consume_seconds = 0.0

    iterator = iter(batch_iter)

    while True:
        t_fetch_start = perf_counter()
        try:
            batch = next(iterator)
        except StopIteration:
            break
        fetch_seconds += perf_counter() - t_fetch_start

        t_consume_start = perf_counter()
        checksum += heavy_consume(batch, mode=mode, sleep_ms=sleep_ms, cpu_repeats=cpu_repeats)
        consume_seconds += perf_counter() - t_consume_start

        rows += int(batch["close"].shape[0])
        batches += 1

    total_seconds = fetch_seconds + consume_seconds
    return PipelineStats(
        name=name,
        rows=rows,
        batches=batches,
        fetch_seconds=fetch_seconds,
        consume_seconds=consume_seconds,
        total_seconds=total_seconds,
        checksum=checksum,
    )


def print_stats(stats: PipelineStats) -> None:
    print(f"\n[{stats.name}]")
    print(f"rows={stats.rows}")
    print(f"batches={stats.batches}")
    print(f"fetch_seconds={stats.fetch_seconds:.6f}")
    print(f"consume_seconds={stats.consume_seconds:.6f}")
    print(f"total_seconds={stats.total_seconds:.6f}")
    if stats.total_seconds > 0:
        print(f"rows_per_sec={stats.rows / stats.total_seconds:,.2f}")
    print(f"checksum={stats.checksum:.6f}")


def main() -> None:
    args = parse_args()

    print(f"data_file={args.data_file}")
    print(f"batch_rows={args.batch_rows}")
    print(f"max_batches={args.max_batches}")
    print(f"consumer_mode={args.consumer_mode}")
    print(f"sleep_ms={args.sleep_ms}")
    print(f"cpu_repeats={args.cpu_repeats}")

    plain = run_pipeline(
        name="plain-stream",
        batch_iter=iter_parquet_batches(args.data_file, args.batch_rows, args.max_batches),
        mode=args.consumer_mode,
        sleep_ms=args.sleep_ms,
        cpu_repeats=args.cpu_repeats,
    )

    prefetch = run_pipeline(
        name="prefetch-stream",
        batch_iter=iter_prefetch_batches(
            args.data_file,
            args.batch_rows,
            args.max_batches,
            args.prefetch_size,
        ),
        mode=args.consumer_mode,
        sleep_ms=args.sleep_ms,
        cpu_repeats=args.cpu_repeats,
    )

    print_stats(plain)
    print_stats(prefetch)

    if prefetch.total_seconds > 0:
        speedup = plain.total_seconds / prefetch.total_seconds
        print("\n[comparison]")
        print(f"speedup_x={speedup:.4f}")
        print(f"time_saved_seconds={plain.total_seconds - prefetch.total_seconds:.6f}")
        print(f"same_checksum={abs(plain.checksum - prefetch.checksum) < 1e-6}")


if __name__ == "__main__":
    main()
