# Accumulative Histogram with Intel TBB (Python)

This example computes a cumulative histogram from a vector of numeric values and compares a sequential implementation with a parallel version that uses the Intel Threading Building Blocks (TBB) Python bindings.

## What it does
- Splits the input vector into blocked ranges so multiple threads count bins concurrently.
- Uses `tbb.parallel_reduce` (classic bindings) or the newer `tbb.pool.Pool` API (recent PyPI wheels) to combine per-range local bin counts safely, then performs a prefix sum to build the accumulative histogram.
- Falls back with a clear error if the TBB bindings are missing.

## Files
- [histogram.py](histogram.py): Sequential and TBB-backed cumulative histogram implementations.
- [main.py](main.py): Simple benchmark/verification driver.
- [requirements.txt](requirements.txt): Python dependency list.

## Quick start
```bash
pip install -r requirements.txt
python main.py
```

## Technical notes on the communication process
- **Work decomposition:** The input vector is divided into `tbb.blocked_range` chunks (`grain_size` controls chunk size). TBB schedules these chunks to worker threads using work-stealing so idle threads pull new blocks, reducing tail latency.
- **Local counting:** Each worker accumulates counts in a thread-local buffer to avoid lock contention while scanning its chunk.
- **Reduction phase:** `parallel_reduce` merges local buffers with a user-defined `join` function, producing the global bin counts without explicit synchronization primitives.
- **Prefix accumulation:** After reduction, a single-thread prefix sum turns raw bin counts into an accumulative histogram (cumulative distribution). This step is O(bins) and negligible compared to the scan.
- **Determinism:** Bin edges are computed once and shared; the reduction order does not affect correctness because only integer additions are performed.

## Parameters you may want to tune
- `bins`: Number of histogram bins.
- `grain_size`: Size of each blocked range passed to TBB; smaller values improve load balance, larger values reduce scheduling overhead.

## Notes
- The TBB Python wheel is published as `tbb` on PyPI. If you see "Parallel version skipped", ensure the package is installed and exposes either `parallel_reduce`/`blocked_range` or `tbb.pool.Pool` (the code will use whichever is available).
- Tested with Python 3.11 on Windows; performance benefits depend on CPU core count and data size.
