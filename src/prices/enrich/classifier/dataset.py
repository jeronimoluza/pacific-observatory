"""Build the (embedding -> head) training table from gold.

The head is trained on gold COICOP *leaf* verdicts for one division (the EAP F&B
PoC is division 01), keeping only leaves with enough support to learn. Training
and eval read one canonical file, ``gold_labels.parquet`` — a DERIVED artifact
that ``consolidate_gold`` unions from the gold_v5_* provenance sources (the 8k
anchor + F&B extra + leaf-targeted expansion rounds). Regenerate it with
``prices label consolidate`` after a new labeling round lands.

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
# Single canonical training/eval gold. DERIVED: `consolidate_gold` unions the
# gold_v5_* provenance files into it; nothing else writes it.
GOLD_LABELS = GOLD_DIR / "gold_labels.parquet"

MIN_SUPPORT = 5


def _gold_sources(gold_dir: Path) -> list[Path]:
    """Provenance files consolidated into gold_labels.parquet, in union order:
    the 8k anchor, the F&B extra, then every leaf-targeted expansion round."""
    return [
        gold_dir / "gold_v5_8k_final.parquet",
        gold_dir / "gold_v5_fnb_extra.parquet",
        *sorted(gold_dir.glob("gold_v5_round*_final.parquet")),
    ]


def consolidate_gold(gold_dir: Path | None = None) -> dict:
    """Union the gold_v5_* provenance files into the single gold_labels.parquet.

    Idempotent: reads only the gold_v5_* sources (never gold_labels.parquet
    itself), so re-running after a new labeling round refreshes the consolidated
    file without re-ingesting its own prior output."""
    gold_dir = gold_dir or GOLD_DIR
    srcs = [p for p in _gold_sources(gold_dir) if p.exists()]
    if not srcs:
        raise FileNotFoundError(f"no gold_v5_* sources under {gold_dir}")
    g = pd.concat([pd.read_parquet(p) for p in srcs], ignore_index=True)
    out = gold_dir / "gold_labels.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    g.to_parquet(out, index=False)
    return {"out": str(out), "n_rows": int(len(g)), "sources": [p.name for p in srcs]}


def _load_gold(gold_dir: Path | None = None) -> pd.DataFrame:
    gold_dir = gold_dir or GOLD_DIR
    labels = gold_dir / "gold_labels.parquet"
    if not labels.exists():
        raise FileNotFoundError(
            f"consolidated gold not found at {labels} — "
            "run `prices label consolidate` to build it from the gold_v5_* sources"
        )
    g = pd.read_parquet(labels)
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
        "gold_sources": [GOLD_LABELS.name],
        "rows_per_source": table["source"].value_counts().to_dict(),
        "rows_per_leaf": table["label"].value_counts().to_dict(),
    }
    Path(vdir / MANIFEST_FILE).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


def load_table(version: str) -> pd.DataFrame:
    return pd.read_parquet(version_dir(version) / TRAIN_FILE)
