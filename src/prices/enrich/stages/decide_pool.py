"""The decide loop, chunk by chunk, optionally across processes.

`classify.run` takes `--workers`, but the flag reached only `be.score`: the loop
underneath it — read a chunk of products_input, run `decide_rows` over it, write
the result — was serial on a sixteen-core box. That loop is not a rounding
error. `decide_rows` is ~90% tier-a regex extraction, which is one pass of the C
regex engine per pattern per name across ~68 patterns, and it measures at
~10.5k rows/s on one core. At 43.1M rows that is ~68 minutes — about as long as
the four-worker scoring pass it follows, so it is roughly half the stage.

Nothing about a chunk depends on any other chunk, so the split is free. What is
not free is how the workers are started, and that is the whole content of this
module.

**Spawn, not fork.** By the time this loop runs the parent holds `scored` — one
entry per scored (name, country) pair, 29.4M of them — plus `unembedded`. A
forked child inherits those pages and never reads them, which sounds like
copy-on-write handles it for free; it does not. CPython writes a refcount into
the header of every object it touches, and a child's first full GC pass walks
the whole heap, so the pages are copied anyway. That is the failure
`hierlex/driver._stage_pairs` was written around, and it OOM-killed a run once
already. A spawned child starts from a fresh interpreter and shares nothing, so
the parent's dict cannot be duplicated N times however large it grows.

**Which means the verdicts have to be shipped, so they are shipped per chunk.**
Spawn pickles each task and 29.4M entries per task is not an option; a chunk
needs only the keys its own rows look up. `classify.row_keys` builds those keys
and is shared with `decide_rows` deliberately — a key built one way in the
subsetter and another way in the loop does not raise, it silently decides the
row as `rejected` with the model's answer sitting unread in the parent.

**Results are consumed in submission order.** The decisions table is written as
one part per country and the classified view is concatenated in arrival order,
so a pool yielding chunks as they finished would produce the same rows in a
different order. Ordered consumption is what makes the parallel output
byte-identical to the serial one, and it costs almost nothing because the
chunks are all about the same size.

**In flight is bounded.** `Executor.map` consumes its whole input iterable up
front, which here means reading all 43.1M rows into memory before the first
worker starts — exactly what the chunked reader exists to prevent. Submitting
into a bounded window keeps the parent holding a handful of chunks instead.

**It is off unless asked for, and it clamps on FREE memory, not total.** This
runs at the point in the stage where the parent is largest, on a box that has
been OOM-killed doing less. `bucket_pool.budget_bytes()` is a fraction of
*physical* RAM, which says the same number whether the machine is idle or has
17 GB already resident — so it is used only as a ceiling here, and the real
limit is what /proc says is available at the moment the pool is built. A
`--workers` that already means "workers for the scoring pass" is deliberately
NOT what switches this on: an existing command line must not silently acquire a
second pool at the most memory-critical moment of the run.
"""

from __future__ import annotations

import multiprocessing
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Iterator, Optional, Sequence

import pandas as pd

from prices.enrich.classifier import bucket_pool
from prices.enrich.stages.products_reader import iter_products

# Measured with `decide_rows` over a real products_input sample: a loaded
# interpreter is ~0.27 GB before the first row, and the chunk, the per-row dicts
# the loop builds and the decision frame it returns come to ~0.8 kB per row.
# 2 kB per row rounds that up to also cover the copy of the chunk the parent
# still holds while the task is in flight. The clamp is deliberately
# pessimistic: being wrong downward costs some parallelism, being wrong upward
# kills a stage whose scoring pass took over an hour.
_WORKER_BASE_BYTES = 350_000_000
_WORKER_BYTES_PER_ROW = 2_000
# What the pool refuses to spend even if the arithmetic says it fits. The
# parent keeps growing while the pool runs (the decision parts it accumulates
# for the classified view), and a box with nothing spare is a box that swaps.
_HEADROOM_BYTES = 4_000_000_000


def available_bytes() -> int:
    """Memory actually free right now, not a fraction of what is installed.

    `MemAvailable` is the kernel's own estimate of what a new process can get
    without swapping, which is the question being asked. Where it cannot be
    read (macOS), fall back to the physical-RAM budget the rest of the
    classifier plans against — that is the pre-existing behaviour, not a
    regression.
    """
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    return bucket_pool.budget_bytes()


def plan_workers(requested: int, chunk_rows: int, budget: int | None = None) -> int:
    """How many decide processes fit. Never fewer than one — one is serial.

    Same shape as `hierlex.driver._plan_workers` and for the same reason: cores
    are not the binding constraint on this box, memory is, and a request for
    more than fits has to become fewer workers — printed — rather than a kill
    two thirds of the way through the corpus.
    """
    per = _WORKER_BASE_BYTES + chunk_rows * _WORKER_BYTES_PER_ROW
    if budget is None:
        budget = min(available_bytes() - _HEADROOM_BYTES, bucket_pool.budget_bytes())
    n = max(1, min(requested, int(budget // per) if budget > 0 else 1))
    if n < requested:
        print(
            f"[classify] {requested} decide workers requested, running {n}: "
            f"{per / 1e9:.1f} GB each against {budget / 1e9:.1f} GB free",
            flush=True,
        )
    return n


def _decide_chunk(task):
    """One chunk, in a worker. Module-level so spawn can pickle it by name."""
    from prices.enrich.stages.classify import decide_rows  # noqa: PLC0415

    chunk, scored, unembedded, key_cols = task
    return decide_rows(chunk, scored, key_cols, unembedded)


def task_for(chunk: pd.DataFrame, scored: dict, key_cols, unembedded):
    """A chunk plus exactly the verdicts and the miss-list its own rows read.

    Both lookups are restricted, never summarized: `scored` keeps the same keys
    mapping to the same tuples and `unembedded` stays a set of names, so the
    worker's `decide_rows` sees inputs indistinguishable from the whole-corpus
    ones for every row it holds. Public because the equivalence test drives it
    directly — the decomposition is the part of this module that can be wrong,
    and it is provable without starting a process.
    """
    from prices.enrich.stages.classify import row_keys  # noqa: PLC0415

    subset = {k: scored[k] for k in row_keys(chunk, key_cols) if k in scored}
    names = set(chunk["product_name_original"].astype(str))
    return chunk, subset, frozenset(unembedded & names), tuple(key_cols)


def iter_decisions(
    in_path: Path,
    chunk_rows: int,
    countries: Optional[Sequence[str]],
    scored: dict,
    key_cols: Sequence[str],
    unembedded: frozenset,
    workers: int = 1,
) -> Iterator[pd.DataFrame]:
    """One decision frame per products chunk, in the order the chunks are read.

    `workers <= 1` is the sequential path exactly as it was — no pool, no task
    building, no subsetting — so a default run is untouched by any of this.
    """
    from prices.enrich.stages.classify import decide_rows  # noqa: PLC0415

    chunks = iter_products(in_path, chunk_rows, countries=countries)
    n = plan_workers(workers, chunk_rows) if workers > 1 else 1
    if n == 1:
        for chunk in chunks:
            yield decide_rows(chunk, scored, key_cols, unembedded)
        return

    # One more task in flight than there are workers: enough that a worker never
    # waits on the parent to read the next chunk, few enough that the parent is
    # never holding the corpus.
    window = n + 1
    ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=n, mp_context=ctx) as pool:
        pending: deque = deque()
        for chunk in chunks:
            task = task_for(chunk, scored, key_cols, unembedded)
            pending.append(pool.submit(_decide_chunk, task))
            if len(pending) >= window:
                yield pending.popleft().result()
        while pending:
            yield pending.popleft().result()
