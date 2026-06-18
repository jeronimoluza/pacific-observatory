"""COICOP anchor / exclude / redirect data layer for tier-b.

Loads the `_sub_labels.parquet` / `_excludes.parquet` sidecars once at import
and exposes them to the index facade: anchor rows (synthetic clusters seeded
from the COICOP authority), the exclude-phrase block map, and the synthetic
anchor-row builder used by build_index. Split out of index.py to keep that
module under the 500-line cap. No logic change versus the pre-split index.py.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Optional

import pandas as pd

# keywords/coicop lives at the enrich/ root, one level above tier_b/.
_COICOP_DIR = Path(__file__).resolve().parent.parent / "keywords" / "coicop"
_ANCHORS_DF: Optional[pd.DataFrame] = None
_EXCLUDES: dict[str, list[str]] = {}
_REDIRECTS: dict[str, list[str]] = {}


def _load_anchors() -> pd.DataFrame:
    p = _COICOP_DIR / "_sub_labels.parquet"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    # Include both anchor and synonym rows: synonym rows carry verbatim JSON ids
    # that match real-cluster sub_label_id values, closing the vocabulary gap.
    return df[df["role"].isin(["anchor", "synonym"])].copy()


def _load_excludes() -> dict[str, list[str]]:
    p = _COICOP_DIR / "_excludes.parquet"
    if not p.exists():
        return {}
    df = pd.read_parquet(p)
    out: dict[str, list[str]] = {}
    for code, grp in df.groupby("coicop_code"):
        out[str(code)] = grp["phrase"].astype(str).tolist()
    return out


def _load_redirects() -> dict[str, list[str]]:
    """Inverse of _load_excludes: map each `excluded_code` (the redirect TARGET)
    to the unique phrases that should pull queries toward it.

    The COICOP authority's excludes are bidirectional information: leaf A says
    'phrase P really belongs at leaf B'. _load_excludes uses the A side as a
    post-retrieval block; this loader uses the B side as embedding-time
    vocabulary so the cosine pulls toward B in the first place.
    """
    p = _COICOP_DIR / "_excludes.parquet"
    if not p.exists():
        return {}
    df = pd.read_parquet(p)
    df = df[df["excluded_code"].notna() & (df["excluded_code"].astype(str) != "")]
    out: dict[str, list[str]] = {}
    for code, grp in df.groupby("excluded_code"):
        phrases: list[str] = []
        seen = set()
        for ph in grp["phrase"].astype(str).tolist():
            key = ph.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            phrases.append(ph.strip())
        if phrases:
            out[str(code)] = phrases
    return out


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFC", s.lower())
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:60]


def _init_module_data() -> None:
    global _ANCHORS_DF, _EXCLUDES, _REDIRECTS
    _ANCHORS_DF = _load_anchors()
    _EXCLUDES = _load_excludes()
    _REDIRECTS = _load_redirects()


_init_module_data()


def excludes() -> dict[str, list[str]]:
    """Accessor for the exclude-phrase block map (code -> phrases)."""
    return _EXCLUDES


def _make_anchor_rows(country: str) -> pd.DataFrame:
    """Build synthetic anchor rows for one country from the loaded anchors DF.
    `sub_label_id` is read directly from the parquet `id` column so anchor IDs
    match the real-cluster vocabulary (both originate from coicop_subcategories.json ids).

    Synonyms fold into one row per (coicop_code, sub_label_id): all labels for
    the same id concatenate into the passage text so e5 sees a denser semantic
    surface (e.g. "Whisky · bourbon · rye whiskey · scotch · single malt").
    """
    if _ANCHORS_DF is None or _ANCHORS_DF.empty:
        return pd.DataFrame()
    has_id_col = "id" in _ANCHORS_DF.columns
    rows = []
    if has_id_col:
        for (code, sl), grp in _ANCHORS_DF.groupby(["coicop_code", "id"], sort=False):
            code = str(code)
            sl = str(sl)
            labels = [str(x) for x in grp["label"].tolist() if str(x).strip()]
            seen = set()
            uniq_labels = []
            for lab in labels:
                key = lab.lower()
                if key in seen:
                    continue
                seen.add(key)
                uniq_labels.append(lab)
            primary = uniq_labels[0] if uniq_labels else sl
            passage = " · ".join(uniq_labels) if uniq_labels else primary
            rows.append(
                {
                    "cluster_id": f"_anchor::{country}::{code}::{sl}",
                    "country": country,
                    "channel": "_anchor",
                    "canonical_strict": passage.lower(),
                    "representative_name": passage,
                    "rep_category": "",
                    "cluster_size": 1,
                    "cluster_agreement_coicop": 1.0,
                    "cluster_agreement_sub_label": 1.0,
                    "coicop_code": code,
                    "sub_label_id": sl,
                    "state": "anchor",
                    "pricing_basis": None,
                    "standard_unit": None,
                    "amount_value": None,
                    "count": 0,
                    "multiplier": None,
                    "is_promotion": False,
                    "is_bundle": False,
                    "is_multipack": False,
                    "promo_reason": None,
                    "confidence": 1.0,
                }
            )
    else:
        for _, r in _ANCHORS_DF.iterrows():
            code = str(r["coicop_code"])
            label = str(r["label"])
            sl = _slug(label)
            rows.append(
                {
                    "cluster_id": f"_anchor::{country}::{code}::{sl}",
                    "country": country,
                    "channel": "_anchor",
                    "canonical_strict": label.lower(),
                    "representative_name": label,
                    "rep_category": "",
                    "cluster_size": 1,
                    "cluster_agreement_coicop": 1.0,
                    "cluster_agreement_sub_label": 1.0,
                    "coicop_code": code,
                    "sub_label_id": sl,
                    "state": "anchor",
                    "pricing_basis": None,
                    "standard_unit": None,
                    "amount_value": None,
                    "count": 0,
                    "multiplier": None,
                    "is_promotion": False,
                    "is_bundle": False,
                    "is_multipack": False,
                    "promo_reason": None,
                    "confidence": 1.0,
                }
            )
    # Redirect anchors: phrases excluded from leaf A and pointed at leaf B
    # become embedding vocabulary on B. sub_label_id="_redirect" — downstream
    # routes to partial_sub_label_pending so tier-c settles the fine label.
    for code, phrases in _REDIRECTS.items():
        passage = " · ".join(phrases)
        rows.append(
            {
                "cluster_id": f"_redirect::{country}::{code}",
                "country": country,
                "channel": "_anchor",
                "canonical_strict": passage.lower(),
                "representative_name": passage,
                "rep_category": "",
                "cluster_size": 1,
                "cluster_agreement_coicop": 1.0,
                "cluster_agreement_sub_label": 0.0,
                "coicop_code": str(code),
                "sub_label_id": "_redirect",
                "state": "anchor",
                "pricing_basis": None,
                "standard_unit": None,
                "amount_value": None,
                "count": 0,
                "multiplier": None,
                "is_promotion": False,
                "is_bundle": False,
                "is_multipack": False,
                "promo_reason": None,
                "confidence": 1.0,
            }
        )
    return pd.DataFrame(rows)
