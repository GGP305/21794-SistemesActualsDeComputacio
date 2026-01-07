"""
Accumulative histogram using sequential and Intel TBB-backed parallel implementations.
The TBB version uses parallel_reduce over blocked ranges; a fallback raises if TBB
is unavailable so callers can decide how to handle it.
"""
from __future__ import annotations

import math
from typing import Iterable, List, Sequence


def _compute_bin_edges(values: Sequence[float], bins: int) -> List[float]:
    if bins <= 0:
        raise ValueError("bins must be positive")
    if not values:
        raise ValueError("values must not be empty")
    v_min = min(values)
    v_max = max(values)
    if math.isclose(v_min, v_max):
        v_max = v_min + 1.0
    width = (v_max - v_min) / bins
    edges = [v_min + i * width for i in range(bins + 1)]
    edges[-1] = v_max
    return edges


def _locate_bin(value: float, edges: Sequence[float], bins: int) -> int:
    span = edges[-1] - edges[0]
    if span <= 0:
        return 0
    raw = int((value - edges[0]) / span * bins)
    return min(max(raw, 0), bins - 1)


def _accumulate_counts(counts: Sequence[int]) -> List[int]:
    running = 0
    out: List[int] = []
    for c in counts:
        running += c
        out.append(running)
    return out


def sequential_accumulative_histogram(values: Iterable[float], bins: int) -> List[int]:
    values_list = list(values)
    edges = _compute_bin_edges(values_list, bins)
    counts = [0 for _ in range(bins)]
    for v in values_list:
        idx = _locate_bin(v, edges, bins)
        counts[idx] += 1
    return _accumulate_counts(counts)


def tbb_accumulative_histogram(values: Iterable[float], bins: int, grain_size: int = 1_000) -> List[int]:
    values_list = list(values)
    edges = _compute_bin_edges(values_list, bins)
    counts = _tbb_histogram_counts(values_list, edges, bins, grain_size)
    return _accumulate_counts(counts)


def _tbb_histogram_counts(values: Sequence[float], edges: Sequence[float], bins: int, grain_size: int) -> List[int]:
    try:
        import tbb  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Intel TBB Python bindings are required for the parallel version. Install with 'pip install tbb'.") from exc

    # Prefer native parallel_reduce if available (older/newer Intel bindings expose it).
    if hasattr(tbb, "parallel_reduce") and hasattr(tbb, "blocked_range"):
        from tbb import blocked_range, parallel_reduce  # type: ignore

        def identity() -> List[int]:
            return [0 for _ in range(bins)]

        def reducer(rng, partial_counts: List[int]) -> List[int]:
            local = [0 for _ in range(bins)]
            for i in range(rng.begin(), rng.end()):
                idx = _locate_bin(values[i], edges, bins)
                local[idx] += 1
            for j in range(bins):
                partial_counts[j] += local[j]
            return partial_counts

        def join(left: List[int], right: List[int]) -> List[int]:
            return [l + r for l, r in zip(left, right)]

        rng = blocked_range(0, len(values), grain_size)
        return parallel_reduce(rng, identity, reducer, join)

    # Newer PyPI packages expose a thread pool API instead of parallel_reduce.
    if hasattr(tbb, "pool"):
        from tbb.pool import Pool  # type: ignore

        def count_chunk(chunk: Sequence[float]) -> List[int]:
            local = [0 for _ in range(bins)]
            for v in chunk:
                idx = _locate_bin(v, edges, bins)
                local[idx] += 1
            return local

        chunks: List[Sequence[float]] = []
        for start in range(0, len(values), grain_size):
            end = min(start + grain_size, len(values))
            chunks.append(values[start:end])

        with Pool() as pool:  # TBB-backed worker pool
            partials = pool.map(count_chunk, chunks)

        total = [0 for _ in range(bins)]
        for part in partials:
            for j in range(bins):
                total[j] += part[j]
        return total

    raise RuntimeError("Installed TBB package lacks both parallel_reduce and pool APIs.")
