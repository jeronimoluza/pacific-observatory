"""The decide pool's decomposition must decide every row the way one frame does.

Starting processes is not what can go wrong here — `ProcessPoolExecutor`
delivering a return value is stdlib contract, and the FIFO deque in
`iter_decisions` is what keeps the order. What can go wrong is the
decomposition around it, and all of it is provable in one process:

  * `row_keys` has to rebuild the score-lookup key exactly as `decide_rows`
    used to inline it. A key that differs does not raise — the row decides as
    `rejected` with the model's verdict sitting unread in the parent, which
    looks like a coverage result rather than a bug.
  * `task_for` has to hand a worker every verdict its chunk reads and no
    others, including for rows whose key columns are absent, null or falsy.
  * chunking must not change any row, so a chunked run concatenates back to
    what the whole frame produces.

So these tests drive `task_for` + `_decide_chunk` directly rather than through a
pool: same code, same inputs, one process.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from prices.enrich.stages import decide_pool
from prices.enrich.stages.classify import decide_rows, row_keys
from prices.enrich.stages.products_reader import PRODUCT_COLS

pytestmark = pytest.mark.unit

KEY_COLS = ("product_name_original", "country")


def _products(n: int = 60) -> pd.DataFrame:
    """A products frame with the shapes the key builder has to survive: a null
    country, an empty one, a name that is only digits, and CJK/latin mixes."""
    names = [
        "Laughing Cow Sliced Cheddar 10s 200g",
        "明治 ブルガリアヨーグルト 400g",
        "Pack of 12 Eggs",
        "Rice 5kg",
        "333'S OLIVES",
        "Paracetamol 500mg 20 Tablets",
    ]
    countries = ["japan", "ghana", None, "", "japan", "italy"]
    rows = []
    for i in range(n):
        rows.append(
            {
                "input_hash": f"h{i:04d}",
                "product_name_original": names[i % len(names)],
                "category": None if i % 5 else "food",
                "country": countries[i % len(countries)],
                "lang": "ja" if i % 3 == 0 else "en",
                "details": "500 g" if i % 7 == 0 else None,
                "unit": None,
                "source": "mangusa_cw" if i % 11 == 0 else "acme",
                "declared_coicop_codes": None,
            }
        )
    return pd.DataFrame(rows)[PRODUCT_COLS]


def _scored(products: pd.DataFrame) -> dict:
    """A verdict for most rows, so both the hit and the miss branch are live."""
    out = {}
    for i, key in enumerate(row_keys(products, KEY_COLS)):
        if i % 4:
            out[key] = ("01.1.1.1.0", 0.9, bool(i % 2), "01.1.1.1.0", 0.8)
    return out


def test_row_keys_reproduces_the_inline_key():
    # The expression `decide_rows` carried before `row_keys` was factored out,
    # applied the way that loop applied it — including the `or ""` that turns a
    # None or an empty country into the same key.
    products = _products()
    columns = [products[c].to_numpy(dtype=object) for c in KEY_COLS]
    expected = [
        tuple(str(v or "") for v in values) for values in zip(*columns)
    ]
    assert list(row_keys(products, KEY_COLS)) == expected


def test_row_keys_fills_an_absent_column_rather_than_raising():
    # products_input predating a key column must key as "", not KeyError — the
    # same tolerance `decide_rows` gets from its `np.full(..., None)` fill.
    products = _products().drop(columns=["country"])
    assert all(k[1] == "" for k in row_keys(products, KEY_COLS))


def test_task_ships_exactly_the_verdicts_the_chunk_reads():
    products = _products()
    scored = _scored(products)
    chunk = products.iloc[10:20]
    _c, subset, unembedded, key_cols = decide_pool.task_for(
        chunk, scored, KEY_COLS, frozenset({"Rice 5kg", "Nowhere Near This Corpus"})
    )
    wanted = {k for k in row_keys(chunk, KEY_COLS) if k in scored}
    assert set(subset) == wanted
    assert all(subset[k] == scored[k] for k in wanted)
    # `unembedded` is restricted to the chunk's own names, and a name the chunk
    # does not carry must not ride along.
    assert unembedded == frozenset({"Rice 5kg"})
    assert key_cols == KEY_COLS


@pytest.mark.parametrize("chunk_rows", [1, 7, 60, 500])
def test_chunked_decomposition_equals_one_frame(chunk_rows):
    products = _products()
    scored = _scored(products)
    unembedded = frozenset({"Rice 5kg"})

    whole = decide_rows(products, scored, KEY_COLS, unembedded)
    parts = [
        decide_pool._decide_chunk(
            decide_pool.task_for(
                products.iloc[i : i + chunk_rows], scored, KEY_COLS, unembedded
            )
        )
        for i in range(0, len(products), chunk_rows)
    ]
    chunked = pd.concat(parts, ignore_index=True)
    pd.testing.assert_frame_equal(whole, chunked)


def test_states_cover_every_branch():
    # An equivalence test over rows that all decide the same way proves very
    # little, so pin that the fixture actually exercises the score hit, the
    # refusal and the never-scored path.
    products = _products()
    dec = decide_rows(products, _scored(products), KEY_COLS, frozenset({"Rice 5kg"}))
    assert {"classified", "rejected", "unembedded"} <= set(dec["state"])


def test_plan_workers_clamps_to_the_budget_and_never_returns_zero():
    per = decide_pool._WORKER_BASE_BYTES + 100_000 * decide_pool._WORKER_BYTES_PER_ROW
    assert decide_pool.plan_workers(8, 100_000, budget=per * 3) == 3
    assert decide_pool.plan_workers(2, 100_000, budget=per * 9) == 2
    # A budget that fits nothing still runs the sequential path rather than
    # raising or returning a pool of zero workers.
    assert decide_pool.plan_workers(8, 100_000, budget=0) == 1
    assert decide_pool.plan_workers(8, 100_000, budget=-1) == 1


def test_available_bytes_is_positive():
    # Reads /proc where there is one and falls back to the physical-RAM budget
    # where there is not; either way a caller can divide by it.
    assert decide_pool.available_bytes() > 0


def test_serial_path_takes_no_pool(tmp_path, monkeypatch):
    # workers=1 must not build tasks, subset anything or import a pool: it is
    # the loop exactly as it was, and that is what a default run gets.
    products = _products()
    scored = _scored(products)
    in_path = tmp_path / "products_input.parquet"
    products.to_parquet(in_path, index=False)

    def boom(*a, **k):  # pragma: no cover - fails the test if reached
        raise AssertionError("serial path must not build pool tasks")

    monkeypatch.setattr(decide_pool, "task_for", boom)
    out = pd.concat(
        decide_pool.iter_decisions(
            in_path, 25, None, scored, KEY_COLS, frozenset(), workers=1
        ),
        ignore_index=True,
    )
    pd.testing.assert_frame_equal(
        out, decide_rows(products, scored, KEY_COLS, frozenset())
    )
