"""Validate the CANDIDATE bucket into trusted unit-value prices + emit the artifact.

For every CANDIDATE row: run tier-a extract(), compute unit_value via the shipped
compute_unit_value (every row is kept — basis mismatches flow through to the
promotion gate, which tags them basis_conflict; nothing is hard-demoted here,
per the 100%-usable principle), render a human-readable calculation string, and
attach FX -> unit_value_usd with the prices FX cache.

write_run writes data/prices/_enrich/validation_runs/{base_item}_YYYYMMDD_HHMM/
with candidates.csv (all promoted rows + the promote gate columns) and green.csv
(the promotion_status==green subset), for review before any promotion downstream.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

import pandas as pd

from prices.build.fx import attach_fx_and_usd
from prices.enrich.config import REPO_ROOT
from prices.enrich.extract import extract
from prices.enrich.normalize import extract_pack
from prices.enrich.stages.merge import compute_unit_value

VALIDATION_RUNS_DIR = REPO_ROOT / "data" / "prices" / "_enrich" / "validation_runs"

ARTIFACT_COLS = [
    "product_name_original",
    "country",
    "source",
    "coicop2digit_title",
    "coicop_deep_leaf_code",
    "base_item",
    "form",
    "variety",
    "currency",
    "original_price",
    "regex_capture",
    "amount_value",
    "pricing_basis",
    "standard_unit",
    "count",
    "multiplier",
    "unit_value_calc_str",
    "unit_value_local",
    "unit_value_usd",
]
# Columns dumped for the non-GREEN buckets (review.csv / exclude.csv / other_form.csv).
NON_GREEN_COLS = [
    "product_name_original",
    "country",
    "source",
    "currency",
    "price",
    "decision",
    "reason",
    "pricing_basis",
]


def _num(x, default=1):
    return default if x is None or (isinstance(x, float) and pd.isna(x)) else x


def _pack_capture(name: str, lang) -> str:
    """The packaging substring tier-a's regex removed + the pattern id that fired
    (e.g. '5kg [PACK_G_KG]'). Recovered by token-diffing the cleaned name."""
    lg = lang if isinstance(lang, str) else None
    cleaned, _c, _v, _u, pack_id = extract_pack(str(name), lg, with_id=True)
    rem = Counter(re.findall(r"\S+", cleaned or ""))
    captured = []
    for tok in re.findall(r"\S+", str(name)):
        if rem.get(tok, 0) > 0:
            rem[tok] -= 1
        else:
            captured.append(tok)
    pack_id = pack_id or "no_match"
    cap = " ".join(captured)
    return f"{cap} [{pack_id}]" if cap else pack_id


def _calc_str(price, currency, sf, uv) -> str:
    unit = sf.standard_unit or "unit"
    count, mult = _num(sf.count), _num(sf.multiplier)
    if sf.pricing_basis in ("mass", "volume", "length"):
        amt = sf.amount_value
        denom = f"{amt}{unit} × {count} × {mult}"
    else:
        denom = f"{count} × {mult} {unit}"
    uv_s = "n/a" if uv is None else f"{uv:.4f}"
    return f"{price} {currency} / ({denom}) = {uv_s} {currency}/{unit}"


def _variety_in(name: str, variety: set[str]) -> str:
    words = set(re.findall(r"[a-z]+", str(name).lower()))
    hit = sorted(words & {v.lower() for v in variety})
    return hit[0] if hit else ""


def validate_green(
    green: pd.DataFrame, rec: dict, base_item: str, timestamp: datetime
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (artifact_df, demoted_df). green needs columns:
    product_name_original, country, currency, price, observation_date, lang.

    Every row is kept and unit-valued; basis mismatches are no longer demoted
    here — the promotion gate tags them basis_conflict downstream. demoted is
    returned empty for signature compatibility."""
    variety_set = rec.get("variety", set())
    leaf = rec["fresh_leaf"]
    div_title = rec.get("coicop2digit_title", "")

    keep, demoted = [], []
    for r in green.itertuples():
        name = r.product_name_original
        sf = extract(
            item_name=str(name),
            category=None,
            country=getattr(r, "country", None),
            lang=getattr(r, "lang", None),
        )
        uv = compute_unit_value(
            r.price, sf.pricing_basis, sf.amount_value, sf.count, sf.multiplier
        )
        keep.append(
            {
                "product_name_original": name,
                "country": r.country,
                "source": getattr(r, "source", "") or "",
                "coicop2digit_title": div_title,
                "coicop_deep_leaf_code": leaf,
                "base_item": base_item,
                "form": "",
                "variety": _variety_in(name, variety_set),
                "currency": r.currency,
                "original_price": r.price,
                "regex_capture": _pack_capture(name, getattr(r, "lang", None)),
                "amount_value": sf.amount_value,
                "pricing_basis": sf.pricing_basis,
                "standard_unit": sf.standard_unit,
                "count": sf.count,
                "multiplier": sf.multiplier,
                "unit_value_calc_str": _calc_str(r.price, r.currency, sf, uv),
                "unit_value_local": uv,
                "observation_date": getattr(r, "observation_date", None),
            }
        )

    art = pd.DataFrame(keep)
    if not art.empty:
        fx_in = art.rename(columns={"unit_value_local": "price_local"})[
            ["price_local", "currency", "observation_date"]
        ].copy()
        fx_out = attach_fx_and_usd(fx_in)
        art["unit_value_usd"] = fx_out["price_usd"].to_numpy()
    else:
        art["unit_value_usd"] = pd.Series(dtype="float64")

    return art[ARTIFACT_COLS], pd.DataFrame(demoted)


_BUCKET_FILES = {
    "CANDIDATE": "candidates.csv",
    "OTHER_FORM": "other_form.csv",
    "REVIEW": "review.csv",
    "EXCLUDE": "exclude.csv",
}


def write_run(
    candidates: pd.DataFrame,
    classified: pd.DataFrame,
    base_item: str,
    timestamp: datetime,
) -> str:
    """candidates: promoted CANDIDATE rows (has promotion_status + gate cols).
    Writes candidates.csv (all) + green.csv (promotion_status==green) + one CSV per
    non-CANDIDATE bucket. Returns the run dir path."""
    from .promote import green_only

    stamp = timestamp.strftime("%Y%m%d_%H%M")
    run_dir = VALIDATION_RUNS_DIR / f"{base_item}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(run_dir / "candidates.csv", index=False)
    if "promotion_status" in candidates.columns:
        green_only(candidates).to_csv(run_dir / "green.csv", index=False)
    else:
        candidates.iloc[0:0].to_csv(run_dir / "green.csv", index=False)
    for bucket, fname in _BUCKET_FILES.items():
        if bucket == "CANDIDATE":
            continue
        sub = classified[classified["decision"] == bucket]
        cols = [c for c in NON_GREEN_COLS if c in sub.columns]
        sub[cols].to_csv(run_dir / fname, index=False)
    return str(run_dir)
