"""
Driver script to compare sequential vs Intel TBB-based accumulative histogram.
"""
from __future__ import annotations

import random
import time
from typing import List

from histogram import sequential_accumulative_histogram, tbb_accumulative_histogram


def generate_values(count: int) -> List[float]:
    rng = random.Random(42)
    return [rng.uniform(-50.0, 150.0) for _ in range(count)]


def run_demo(size: int = 1_000_000, bins: int = 128) -> None:
    values = generate_values(size)

    t0 = time.perf_counter()
    seq = sequential_accumulative_histogram(values, bins)
    t1 = time.perf_counter()

    t2 = time.perf_counter()
    try:
        par = tbb_accumulative_histogram(values, bins)
    except RuntimeError as exc:
        print("Parallel version skipped:", exc)
        return
    t3 = time.perf_counter()

    print(f"Data points: {size}, bins: {bins}")
    print(f"Sequential time: {(t1 - t0)*1000:.2f} ms")
    print(f"TBB parallel time: {(t3 - t2)*1000:.2f} ms")
    print(f"Results match: {seq == par}")
    print(f"Last bin cumulative count: {par[-1] if par else 0}")


if __name__ == "__main__":
    run_demo()
