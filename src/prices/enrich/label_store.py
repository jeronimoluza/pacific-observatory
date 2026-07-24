import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from prices.enrich import config
from prices.enrich.keys import norm_key

LABEL_STORE_PATH = config.ENRICH_DIR / "label_store.parquet"

DECISIONS = {"leaf", "exclude", "other_form", "ambiguous_class"}
TIERS = {"T0_memo", "T0_lexicon", "T1_consensus", "T2_model", "T3_adjudicated"}

COLUMNS = [
    "row_id",
    "canonical_key",
    "leaf",
    "decision",
    "class_code",
    "tier",
    "confidence",
    "witness_votes",
    "model_version",
    "lexicon_version",
    "provenance",
    "created_at",
    "superseded_by",
]

_REQUIRED = {"canonical_key", "decision", "tier", "provenance"}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_utc(val) -> str:
    if isinstance(val, datetime):
        if val.tzinfo is None or val.utcoffset() != timezone.utc.utcoffset(None):
            raise ValueError(f"created_at must be UTC tz-aware, got {val!r}")
        return val.isoformat()
    parsed = datetime.fromisoformat(str(val))
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError(f"created_at must be UTC, got {val!r}")
    return str(val)


def _empty() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in COLUMNS})


def load(path=LABEL_STORE_PATH) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return _empty()
    df = pd.read_parquet(p)
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = pd.NA
    return df[COLUMNS]


def _coerce_votes(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "{}"
    if isinstance(val, str):
        return val
    return json.dumps(val, ensure_ascii=False, sort_keys=True)


def append(df, path=LABEL_STORE_PATH) -> pd.DataFrame:
    rows = pd.DataFrame(df).copy()
    if rows.empty:
        return _empty()
    missing = _REQUIRED - set(rows.columns)
    if missing:
        raise ValueError(f"append missing required columns: {sorted(missing)}")

    bad_dec = set(rows["decision"].dropna().unique()) - DECISIONS
    if bad_dec:
        raise ValueError(f"invalid decision values: {sorted(bad_dec)}")
    bad_tier = set(rows["tier"].dropna().unique()) - TIERS
    if bad_tier:
        raise ValueError(f"invalid tier values: {sorted(bad_tier)}")

    rows["canonical_key"] = rows["canonical_key"].map(norm_key)
    if (rows["canonical_key"].str.len() == 0).any():
        raise ValueError("append produced empty canonical_key after normalization")

    if "created_at" in rows.columns:
        rows["created_at"] = rows["created_at"].map(
            lambda v: _utcnow()
            if v is None or (isinstance(v, float) and pd.isna(v))
            else _ensure_utc(v)
        )
    else:
        rows["created_at"] = _utcnow()

    rows["row_id"] = [str(uuid.uuid4()) for _ in range(len(rows))]
    rows["superseded_by"] = pd.NA
    rows["witness_votes"] = rows.get(
        "witness_votes", pd.Series([None] * len(rows))
    ).map(_coerce_votes)

    for c in COLUMNS:
        if c not in rows.columns:
            rows[c] = pd.NA
    rows = rows[COLUMNS]

    existing = load(path)
    out = pd.concat([existing, rows], ignore_index=True)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(p, index=False)
    return rows


def active(path=LABEL_STORE_PATH) -> pd.DataFrame:
    df = load(path)
    if df.empty:
        return df
    live = df[df["superseded_by"].isna()]
    live = live.sort_values(["canonical_key", "created_at", "row_id"])
    return live.drop_duplicates("canonical_key", keep="last").reset_index(drop=True)


def lookup(keys, path=LABEL_STORE_PATH) -> pd.DataFrame:
    wanted = {norm_key(k) for k in keys}
    act = active(path)
    if act.empty:
        return act
    return act[act["canonical_key"].isin(wanted)].reset_index(drop=True)


def supersede(row_ids, by, path=LABEL_STORE_PATH) -> int:
    df = load(path)
    if df.empty:
        return 0
    ids = set(row_ids)
    mask = df["row_id"].isin(ids) & df["superseded_by"].isna()
    n = int(mask.sum())
    if n:
        df.loc[mask, "superseded_by"] = by
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(Path(path), index=False)
    return n
