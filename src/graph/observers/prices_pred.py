"""`prices.scored`: the hierlex pred buckets `pred_NNN.parquet` (+ `.fingerprint.json`) and
their `_pairs/pairs_NNN.parquet`, one row per bucket 000-255.

SHA is the fingerprint's `bundle_sha`. Drift: a bucket missing, its fingerprint missing
or naming another scorer than the bundle directory, and its pairs file missing.
"""

from __future__ import annotations

import json
from pathlib import Path

from graph.observe import mtime, node_path, parquet_rows, row

BUCKETS = 256


def observe(node) -> list[dict]:
    pred_dir = Path(node_path(node, "output", "pred_")).parent
    if not pred_dir.is_dir():
        return []
    out = []
    for b in range(BUCKETS):
        pred = pred_dir / f"pred_{b:03d}.parquet"
        fp_file = pred_dir / f"pred_{b:03d}.parquet.fingerprint.json"
        fp = json.loads(fp_file.read_text()) if fp_file.exists() else {}
        drift = []
        if not pred.exists():
            drift.append("pred_missing")
        if not fp:
            drift.append("fingerprint_missing")
        elif fp.get("scorer_version") != pred_dir.name:
            drift.append(
                f"scorer_version {fp.get('scorer_version')} != {pred_dir.name}"
            )
        if not (pred_dir / "_pairs" / f"pairs_{b:03d}.parquet").exists():
            drift.append("pairs_missing")
        out.append(
            row(
                node,
                f"bucket_{b:03d}",
                pred.exists(),
                parquet_rows(pred) if pred.exists() else None,
                mtime(pred),
                (fp.get("bundle_sha") or "")[:12] or None,
                drift,
                {"blocks": [blk[0] for blk in fp.get("blocks", [])]},
            )
        )
    return out
