"""Local embedding-neighborhood agreement for every gold row.

A gold label that disagrees with the labels of its nearest neighbours in
embedding space is either a genuinely hard case or a mistake. Either way it is
worth an adjudicator's attention, and finding it costs nothing: the vectors are
already on disk under ``_embed_store/``, so this is a matrix multiply, not an
LLM call.

Neighbours are searched **within a division**. Cross-division neighbours are
uninformative here — a head only ever chooses among leaves of one division, and
a rice product's nearest non-food neighbour tells the audit nothing about
whether its leaf is right.

Similarity is plain dot product. Every block in the ensemble is L2-normalized
per row before concatenation, so the dot product of two ensemble vectors is the
sum of per-block cosines — monotone in the similarity the head itself sees.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from prices.enrich import embedding
from prices.enrich.classifier.dataset import _load_gold
from prices.enrich.gold_audit import NEIGHBORS_FILE, ensure_run_dir, run_dir

DEFAULT_K = 15
# Chunked so a division's full similarity matrix never has to exist at once:
# 24k x 24k float32 would be 2.3 GB for division 01 alone.
QUERY_CHUNK = 512


def _topk_within(mat: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Row-wise top-k by dot product, excluding each row's own self-match.

    Returns `(idx, sim)` both shaped (n, k) with row-local indices."""
    n = len(mat)
    k = min(k, n - 1)
    idx = np.zeros((n, k), np.int32)
    sim = np.zeros((n, k), np.float32)

    for start in range(0, n, QUERY_CHUNK):
        stop = min(start + QUERY_CHUNK, n)
        block = mat[start:stop] @ mat.T
        # Mask self so a row is never its own neighbour.
        block[np.arange(stop - start), np.arange(start, stop)] = -np.inf
        part = np.argpartition(-block, kth=k - 1, axis=1)[:, :k]
        part_sim = np.take_along_axis(block, part, axis=1)
        order = np.argsort(-part_sim, axis=1)
        idx[start:stop] = np.take_along_axis(part, order, axis=1)
        sim[start:stop] = np.take_along_axis(part_sim, order, axis=1)

    return idx, sim


def _division_frame(
    codes: np.ndarray, row_ids: np.ndarray, idx: np.ndarray, sim: np.ndarray
) -> pd.DataFrame:
    neighbor_codes = codes[idx]
    own = codes[:, None]

    purity = (neighbor_codes == own).mean(axis=1).astype(np.float32)

    majority = []
    for row in neighbor_codes:
        vals, counts = np.unique(row, return_counts=True)
        majority.append(vals[counts.argmax()])
    majority = np.asarray(majority, dtype=object)

    return pd.DataFrame(
        {
            "gold_row_id": row_ids,
            "purity_at_k": purity,
            "neighbor_majority_code": majority.astype(str),
            "neighbor_disagrees": majority != codes,
            "top1_sim": sim[:, 0],
            "top1_code": neighbor_codes[:, 0].astype(str),
            "n_neighbors": idx.shape[1],
        }
    )


def compute(
    run_id: str, k: int = DEFAULT_K, divisions: list[str] | None = None
) -> dict:
    """Write ``neighbors.parquet`` for the run: one row per gold row that had at
    least one same-division neighbour to compare against."""
    gold = _load_gold().reset_index(drop=True)
    wanted = divisions or sorted(gold["division"].dropna().unique())

    frames: list[pd.DataFrame] = []
    skipped: dict[str, int] = {}

    for div in wanted:
        part = gold[gold["division"] == div]
        if len(part) < 2:
            skipped[div] = int(len(part))
            continue
        mat = embedding.embed_names(part["product_name"].astype(str).tolist())
        idx, sim = _topk_within(mat, k)
        frames.append(
            _division_frame(
                part["code"].to_numpy(dtype=object),
                part["gold_row_id"].to_numpy(),
                idx,
                sim,
            )
        )

    out = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=["gold_row_id"])
    )
    out.to_parquet(ensure_run_dir(run_id) / NEIGHBORS_FILE, index=False)

    return {
        "run_id": run_id,
        "k": k,
        "n_rows": int(len(out)),
        "n_disagree": int(out["neighbor_disagrees"].sum()) if len(out) else 0,
        "divisions_skipped": skipped,
    }


def load(run_id: str) -> pd.DataFrame:
    return pd.read_parquet(run_dir(run_id) / NEIGHBORS_FILE)
