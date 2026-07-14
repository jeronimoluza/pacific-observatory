"""Build the (embedding -> head) training table from gold.

The head is trained on gold COICOP *leaf* verdicts for one division (the EAP F&B
PoC is division 01), keeping only leaves with enough support to learn. Two gold
sources are unioned in the canonical 8k schema:

  - ``gold_v5_8k_final.parquet``  — the canonical 8k gold (codex+gemini agreement,
    opus-adjudicated hard cases).
  - ``gold_v5_fnb_extra.parquet`` — wild-labeled F&B agreement/adjudicated rows
    (fnbdl-*) that lift deep-leaf coverage.

The RAW ``product_name`` is stored verbatim (normalization hurts — the embedder
sees raw text). Emits ``train.parquet`` (name/label/division/source) +
``training_manifest.json`` into the version directory.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from prices.enrich import config
from prices.enrich.classifier import MANIFEST_FILE, TRAIN_FILE, version_dir

GOLD_DIR = config.REPO_ROOT / "data" / "prices" / "enrich" / "gold"
GOLD_MAIN = GOLD_DIR / "gold_v5_8k_final.parquet"
GOLD_EXTRA = GOLD_DIR / "gold_v5_fnb_extra.parquet"

MIN_SUPPORT = 5


def _load_gold() -> pd.DataFrame:
    frames = []
    for p in (GOLD_MAIN, GOLD_EXTRA):
        if p.exists():
            frames.append(pd.read_parquet(p))
    if not frames:
        raise FileNotFoundError(f"no gold under {GOLD_DIR}")
    g = pd.concat(frames, ignore_index=True)
    g["code"] = g["code"].astype(str)
    g["division"] = g["code"].str.split(".").str[0]
    return g


def build(
    version: str,
    division: str = config.CLASSIFIER_DEFAULT_DIVISION,
    min_support: int = MIN_SUPPORT,
) -> dict:
    g = _load_gold()
    g = g[(g["verdict"] == "leaf") & (g["division"] == division)].copy()
    vc = g["code"].value_counts()
    keep = set(vc[vc >= min_support].index)
    g = g[g["code"].isin(keep)].reset_index(drop=True)

    table = pd.DataFrame(
        {
            "name": g["product_name"].astype(str),
            "label": g["code"],
            "division": g["division"],
            "source": g.get("label_source", pd.Series([""] * len(g)))
            .fillna("")
            .astype(str),
        }
    )

    vdir = version_dir(version)
    vdir.mkdir(parents=True, exist_ok=True)
    table.to_parquet(vdir / TRAIN_FILE, index=False)

    manifest = {
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "division": division,
        "min_support": min_support,
        "n_rows": int(len(table)),
        "n_leaves": int(table["label"].nunique()),
        "gold_sources": [p.name for p in (GOLD_MAIN, GOLD_EXTRA) if p.exists()],
        "rows_per_source": table["source"].value_counts().to_dict(),
        "rows_per_leaf": table["label"].value_counts().to_dict(),
    }
    Path(vdir / MANIFEST_FILE).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


def load_table(version: str) -> pd.DataFrame:
    return pd.read_parquet(version_dir(version) / TRAIN_FILE)
