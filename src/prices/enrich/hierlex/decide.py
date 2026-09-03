"""Turn HierLex shards into the pipeline's decisions table.

The shards carry model output only. Everything else a decision row needs —
structural regex extraction, the source-declared narrow-COICOP short-circuit, the
basis audit — is pipeline behaviour that has nothing to do with which classifier
produced the leaf, so this reuses `stages.classify.decide_rows` rather than
restating it. The result is schema-identical to the in-house head's output and
lands in the same place, which is what lets `prices build` consume either.

Iteration is bucket-major on both sides: products are sorted by their name's
store bucket so each shard is read once and only that bucket's score maps are
resident. Keying maps for all 7.29M pairs at once would cost several GB for no
benefit.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from prices.enrich import config
from prices.enrich.classifier import embed_store
from prices.enrich.hierlex import driver, package, scorer, vectors
from prices.enrich.stages.classify import (
    DECISION_SCHEMA,
    PRODUCT_COLS,
    classified_view,
    decide_rows,
)
from prices.enrich.stages.merge import ENRICHMENT_COLS

_COUNTRY = "_hlx_country"


# The grain HierLex decides at. `decide_rows` looks its score dict up on these
# columns, so they name columns of the *products* frame, not of the shard.
KEY_COLS = ("product_name_original", _COUNTRY)


def _bucket_maps(shard: pd.DataFrame, tau: float) -> tuple[dict, set]:
    """One bucket's shard as the (key -> verdict) dict `decide_rows` expects.

    `conf` is the leaf softmax score and `gate_score` the calibrated meta-gate
    score: two different numbers, and acceptance is a threshold on the second.
    Collapsing them would make a confident leaf behind a doubtful gate
    indistinguishable from the reverse.
    """
    keys = list(zip(shard["name"].astype(str), shard["country"].astype(str)))
    acc = (shard["calibrated_correctness_score"].to_numpy() >= tau).astype(bool)
    is_leaf = shard["is_leaf"].to_numpy().astype(bool)
    ok = acc & is_leaf
    scored = dict(
        zip(
            keys,
            zip(
                shard["assigned_coicop"].astype(str),
                shard["original_score"].astype(float),
                ok.tolist(),
                shard["proposed_leaf"].astype(str),
                shard["calibrated_correctness_score"].astype(float),
            ),
        )
    )
    # Accepted, but the fallback landed on a parent with no "n.e.c." leaf, so
    # `final_action` is the synthetic `<parent>.__parent_fallback__` token. That
    # is a real decision at parent grain and must not be filed as a refusal.
    fallback_parent = {k for k, a, lf in zip(keys, acc, is_leaf) if a and not lf}
    return scored, fallback_parent


def _decide_bucket(
    group: pd.DataFrame, shard: pd.DataFrame, tau: float
) -> pd.DataFrame:
    names = group["product_name_original"].astype(str).unique().tolist()
    _, unembedded = vectors.split_by_store_coverage(names)
    scored, fb = _bucket_maps(shard, tau)
    dec = decide_rows(group, scored, KEY_COLS, unembedded)
    if fb:
        keys = list(zip(group["product_name_original"].astype(str), group[_COUNTRY]))
        mask = np.fromiter((k in fb for k in keys), dtype=bool, count=len(keys))
        dec.loc[mask & (dec["state"] == "rejected"), "state"] = "fallback_parent"
    return dec


def _load_products(in_path: Path, wanted: set[int] | None):
    """Products plus their store bucket, restricted to `wanted` when given.

    A progressive poll decides only the buckets that already have a score shard.
    Materializing all 37M products to reach a tenth of them costs ~15 GB of
    Python strings on a box that is busy scoring, so when a subset is asked for
    the row groups are streamed and non-target rows are dropped before anything
    is concatenated -- peak is one row group plus the rows actually kept.
    `wanted=None` keeps the single-read path, which is what the final full run
    wants once scoring has released its memory.
    """
    if wanted is None:
        products = pd.read_parquet(in_path, columns=PRODUCT_COLS)
        bucket = np.fromiter(
            (
                embed_store.bucket_of(n)
                for n in products["product_name_original"].astype(str)
            ),
            dtype=np.int16,
            count=len(products),
        )
        return products, bucket

    pf = pq.ParquetFile(in_path)
    keep_ids = np.array(sorted(wanted), dtype=np.int16)
    frames, buckets = [], []
    for rg in range(pf.metadata.num_row_groups):
        chunk = pf.read_row_group(rg, columns=PRODUCT_COLS).to_pandas()
        bkt = np.fromiter(
            (
                embed_store.bucket_of(n)
                for n in chunk["product_name_original"].astype(str)
            ),
            dtype=np.int16,
            count=len(chunk),
        )
        sel = np.isin(bkt, keep_ids)
        if sel.any():
            frames.append(chunk[sel])
            buckets.append(bkt[sel])
        del chunk, bkt
    if not frames:
        return pd.DataFrame(columns=PRODUCT_COLS), np.empty(0, dtype=np.int16)
    return pd.concat(frames, ignore_index=True), np.concatenate(buckets)


def run(
    version: str | None = None,
    policy: str = "conservative_risk",
    in_path: Path | None = None,
    out_path: Path | None = None,
    full_out_path: Path | None = None,
    pred_root: Path = driver.PRED_ROOT,
    scored_only: bool = False,
) -> dict:
    """Write the decisions table (and the division-01 view) from HierLex shards.

    `scored_only` limits the pass to buckets that already carry a score shard.
    Every other bucket would decide as a refusal and contribute nothing to the
    classified view, so skipping them makes a mid-scoring poll cheap enough to
    run beside the scorer instead of having to stop it.
    """
    if policy not in scorer.POLICIES:
        raise ValueError(
            f"unknown policy {policy!r}; expected one of {scorer.POLICIES}"
        )
    pkg = package.resolve(version)
    meta = package.manifest(pkg)
    tau = float(meta["thresholds"]["thresholds"][f"lexical_correctness_gate_{policy}"])
    shard_dir = pred_root / meta["method_version"]
    if not any(shard_dir.glob("pred_*.parquet")):
        raise FileNotFoundError(
            f"no HierLex shards under {shard_dir} — run `prices hierlex score` first"
        )

    in_path = in_path or config.PRODUCTS_INPUT_PARQUET
    out_path = out_path or config.CLASSIFIED_HIERLEX_PARQUET
    full_out_path = full_out_path or config.DECISIONS_HIERLEX_PARQUET
    full_out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    scored = {int(p.stem.rsplit("_", 1)[1]) for p in shard_dir.glob("pred_*.parquet")}
    targets = sorted(scored) if scored_only else list(range(embed_store.N_BUCKETS))

    # Streaming only pays off while it discards rows. Once every bucket is a
    # target it would concatenate the whole table on top of the chunks it read,
    # which is strictly worse than reading it once.
    partial = len(targets) < embed_store.N_BUCKETS
    products, bucket = _load_products(in_path, set(targets) if partial else None)
    products[_COUNTRY] = products["country"].fillna("missing").astype(str).str.lower()
    order = np.argsort(bucket, kind="stable")
    bounds = np.searchsorted(bucket[order], np.arange(embed_store.N_BUCKETS + 1))

    # Per-bucket decision shards, mirroring how `score` shards its own output.
    # Deciding is a full pass over every product, so without this a progressive
    # run redoes all 256 buckets each round just to pick up the few that gained
    # a score shard -- and a kill mid-run loses the whole pass. A shard is reused
    # only when it is newer than the score shard it was derived from, so a
    # rescored bucket invalidates its own decision.
    dec_dir = shard_dir / "_decisions"
    dec_dir.mkdir(parents=True, exist_ok=True)

    writer = None
    views: list[pd.DataFrame] = []
    n_dec = 0
    n_reused = 0
    try:
        for b in targets:
            idx = order[bounds[b] : bounds[b + 1]]
            if len(idx) == 0:
                continue
            part = shard_dir / f"pred_{b:03d}.parquet"
            dec_part = dec_dir / f"dec_{b:03d}.parquet"
            fresh = dec_part.exists() and (
                not part.exists() or dec_part.stat().st_mtime >= part.stat().st_mtime
            )
            if fresh:
                dec = pd.read_parquet(dec_part)
                n_reused += 1
            else:
                shard = (
                    pd.read_parquet(part)
                    if part.exists()
                    else pd.DataFrame(
                        columns=[
                            "name",
                            "country",
                            "assigned_coicop",
                            "proposed_leaf",
                            "is_leaf",
                            "original_score",
                            "calibrated_correctness_score",
                        ]
                    )
                )
                dec = _decide_bucket(products.take(idx), shard, tau)
                tmp = dec_part.with_suffix(".parquet.tmp")
                pq.write_table(
                    pa.Table.from_pandas(
                        dec, schema=DECISION_SCHEMA, preserve_index=False
                    ),
                    tmp,
                )
                tmp.replace(dec_part)
            n_dec += len(dec)
            views.append(classified_view(dec, config.BUILD_DIVISIONS))
            table = pa.Table.from_pandas(
                dec, schema=DECISION_SCHEMA, preserve_index=False
            )
            if writer is None:
                writer = pq.ParquetWriter(full_out_path, DECISION_SCHEMA)
            writer.write_table(table)
            print(
                f"[hierlex decide] bucket {b:3d}: {n_dec:,}/{len(products):,}"
                f"{' (reused)' if fresh else ''}",
                flush=True,
            )
    finally:
        if writer is not None:
            writer.close()

    view = (
        pd.concat(views, ignore_index=True)
        if views
        else pd.DataFrame(columns=[*ENRICHMENT_COLS, "input_hash"])
    )
    view.to_parquet(out_path, index=False)
    return {
        "method_version": meta["method_version"],
        "policy": policy,
        "tau": tau,
        "decisions": n_dec,
        "buckets_decided": len(targets),
        "buckets_scored": len(scored),
        "buckets_reused": n_reused,
        "partial": partial,
        "decisions_path": str(full_out_path),
        "classified": len(view),
        "classified_path": str(out_path),
    }
