"""Backfill NSW FuelCheck historical resources.

This is intentionally separate from the regular update pipeline because
FuelCheck publishes monthly files (CSV/XLSX) and a full backfill can be large.
We stream each monthly resource into the per-source observations file.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from .constants import COLUMNS, FETCH_STATE_JSON
from .fuelcheck_resources import (
    DATASET_URL,
    load_package_resources,
    parse_resource_bytes,
    pick_best_resources_per_period,
)
from .storage import source_csv_path
from .utils import get_session, make_template


_FUEL_CODE_FIELDS = {
    # FuelCheck code -> canonical fields
    "E10": {
        "fuel_family": "gasoline",
        "fuel_product": "E10",
        "quality_group": "regular",
        "octane_ron": 91,
        "ethanol_pct": 10,
    },
    "U91": {
        "fuel_family": "gasoline",
        "fuel_product": "Unleaded 91",
        "quality_group": "regular",
        "octane_ron": 91,
        "ethanol_pct": 0,
    },
    "P95": {
        "fuel_family": "gasoline",
        "fuel_product": "Premium 95",
        "quality_group": "premium",
        "octane_ron": 95,
        "ethanol_pct": 0,
    },
    "P98": {
        "fuel_family": "gasoline",
        "fuel_product": "Premium 98",
        "quality_group": "premium",
        "octane_ron": 98,
        "ethanol_pct": 0,
    },
    "E20": {
        "fuel_family": "gasoline",
        "fuel_product": "E20",
        "quality_group": None,
        "octane_ron": None,
        "ethanol_pct": 20,
    },
    "E85": {
        "fuel_family": "gasoline",
        "fuel_product": "E85",
        "quality_group": None,
        "octane_ron": None,
        "ethanol_pct": 85,
    },
    "DL": {
        "fuel_family": "diesel",
        "fuel_product": "Diesel",
        "quality_group": "standard",
        "octane_ron": None,
        "ethanol_pct": None,
    },
    "LPG": {
        "fuel_family": "lpg",
        "fuel_product": "LPG",
        "quality_group": "standard",
        "octane_ron": None,
        "ethanol_pct": None,
    },
}


_TMPL = make_template(
    country="Australia",
    wb_iso3="AUS",
    source_key="au_nsw_fuelcheck_history",
    source_name="NSW FuelCheck price history",
    source_url=DATASET_URL,
    currency="AUD",
    unit="L",
    subnational_area="New South Wales",
    publication_frequency="monthly",
    observation_method="reported",
    source_type="official",
)


def _pick_col(df: pd.DataFrame, *names: str) -> str | None:
    col_lookup = {str(c).replace(" ", "").lower(): c for c in df.columns}
    for name in names:
        key = name.replace(" ", "").lower()
        if key in col_lookup:
            return str(col_lookup[key])
    return None


def _maybe_promote_header(df: pd.DataFrame) -> pd.DataFrame:
    """Some early XLSX resources embed the real header row as the first row."""
    required_keys = {"fuelcode", "priceupdateddate", "price"}
    for i in range(min(6, len(df))):
        row = df.iloc[i]
        vals = {
            str(v).replace(" ", "").strip().lower()
            for v in row.tolist()
            if v is not None
        }
        if required_keys.issubset(vals):
            df2 = df.iloc[i + 1 :].copy()
            df2.columns = [str(v).strip() for v in row.tolist()]
            return df2
    return df


def _canonicalize(df: pd.DataFrame) -> pd.DataFrame:
    df = _maybe_promote_header(df)
    # Resolve required columns
    col_fuel = _pick_col(df, "FuelCode", "FuelType")
    col_updated = _pick_col(df, "PriceUpdatedDate")
    col_price = _pick_col(df, "Price")
    col_suburb = _pick_col(df, "Suburb")
    if col_fuel is None or col_updated is None or col_price is None:
        raise ValueError("Missing required columns")

    obs_ts = pd.to_datetime(df[col_updated], errors="coerce", utc=True)
    obs_date = obs_ts.dt.date
    raw_price = pd.to_numeric(df[col_price], errors="coerce")
    price = pd.Series(
        [
            (float(value) / 100.0) if pd.notna(value) and float(value) >= 10 else value
            for value in raw_price
        ],
        index=df.index,
        dtype="float64",
    )
    fuel_code = df[col_fuel].astype(str).str.strip().str.upper()

    out = pd.DataFrame(index=df.index)
    out["country"] = _TMPL["country"]
    out["wb_iso3"] = _TMPL["wb_iso3"]
    out["subnational_area"] = _TMPL["subnational_area"]
    if col_suburb is not None and col_suburb in df.columns:
        sub = df[col_suburb]
        out["city"] = (
            sub.astype(str)
            .where(sub.notna(), None)
            .map(lambda x: x.strip() if isinstance(x, str) else x)
        )
    else:
        out["city"] = None
    out["currency"] = _TMPL["currency"]
    out["unit"] = _TMPL["unit"]
    out["tax_status"] = _TMPL["tax_status"]
    out["source_key"] = _TMPL["source_key"]
    out["source_name"] = _TMPL["source_name"]
    out["source_url"] = _TMPL["source_url"]
    out["source_type"] = _TMPL["source_type"]
    out["publication_frequency"] = _TMPL["publication_frequency"]
    out["observation_method"] = _TMPL["observation_method"]
    out["consumer_segment"] = _TMPL["consumer_segment"]
    out["status"] = _TMPL["status"]

    out["price_local"] = price.round(4)
    out["observation_date"] = obs_date.astype(str)
    out["effective_from"] = out["observation_date"]
    out["effective_to"] = out["observation_date"]

    fam_map = {k: v.get("fuel_family") for k, v in _FUEL_CODE_FIELDS.items()}
    prod_map = {k: v.get("fuel_product") for k, v in _FUEL_CODE_FIELDS.items()}
    qg_map = {k: v.get("quality_group") for k, v in _FUEL_CODE_FIELDS.items()}
    ron_map = {k: v.get("octane_ron") for k, v in _FUEL_CODE_FIELDS.items()}
    eth_map = {k: v.get("ethanol_pct") for k, v in _FUEL_CODE_FIELDS.items()}

    out["fuel_family"] = fuel_code.map(fam_map)
    out["fuel_product"] = fuel_code.map(prod_map).fillna(fuel_code)
    out["quality_group"] = fuel_code.map(qg_map)
    out["octane_ron"] = fuel_code.map(ron_map)
    out["ethanol_pct"] = fuel_code.map(eth_map)

    # Filter invalid rows
    ok = (
        out["observation_date"].notna()
        & out["price_local"].notna()
        & (out["price_local"] > 0)
        & (out["price_local"] >= 0.5)
        & (out["price_local"] <= 4.0)
    )
    out = out.loc[ok].copy()

    # Ensure required columns exist
    for c in COLUMNS:
        if c not in out.columns:
            out[c] = None
    out = out[COLUMNS]
    # Skip hash computation for backfills (expensive and not required for the
    # append-only historical dump). Downstream deduping can be computed later.
    out["observation_hash"] = None
    return out


def backfill_nsw_fuelcheck(
    *,
    overwrite: bool = False,
    from_period: tuple[int, int] | None = None,
    to_period: tuple[int, int] | None = None,
) -> Path:
    """Download all historical FuelCheck resources and write a single observations.csv.

    Returns the output path.
    """
    out_path = source_csv_path("Australia", "au_nsw_fuelcheck_history")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    resume_after: tuple[int, int] | None = None
    if out_path.exists() and not overwrite:
        try:
            existing_dates = pd.read_csv(out_path, usecols=["observation_date"])  # type: ignore[arg-type]
            dmax = pd.to_datetime(
                existing_dates["observation_date"], errors="coerce"
            ).max()
            if pd.notna(dmax):
                resume_after = (int(dmax.year), int(dmax.month))
                print(
                    f"  [fuelcheck_backfill] Resuming after {resume_after[0]}-{resume_after[1]:02d}"
                )
        except Exception:
            resume_after = None

    resources = pick_best_resources_per_period(load_package_resources())
    if not resources:
        raise RuntimeError("No FuelCheck price history resources found")

    session = get_session()
    wrote_header = out_path.exists() and not overwrite
    max_obs: date | None = None
    manifest_path = out_path.parent / "manifest.json"
    manifest_by_id: dict[str, dict] = {}
    if manifest_path.exists() and not overwrite:
        try:
            prev = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(prev, list):
                for it in prev:
                    if isinstance(it, dict) and it.get("id"):
                        manifest_by_id[str(it["id"])] = it
        except Exception:
            manifest_by_id = {}

    if overwrite and out_path.exists():
        out_path.unlink()

    for i, r in enumerate(resources, start=1):
        if r.year and r.month:
            period = (r.year, r.month)
            if from_period is not None and period < from_period:
                continue
            if to_period is not None and period > to_period:
                continue
            if (
                from_period is None
                and resume_after is not None
                and period <= resume_after
            ):
                continue
        print(f"  [fuelcheck_backfill] ({i}/{len(resources)}) {r.name} ({r.fmt})")
        resp = session.get(r.url, timeout=120)
        resp.raise_for_status()
        raw = parse_resource_bytes(resp.content, r.fmt)
        if raw is None or raw.empty:
            continue

        try:
            canon = _canonicalize(raw)
        except Exception as e:
            print(f"  [fuelcheck_backfill] Skip (parse/canonicalize failed): {e}")
            continue

        if canon.empty:
            continue

        # Track max observation_date
        try:
            d = pd.to_datetime(canon["observation_date"], errors="coerce").max()
            if pd.notna(d):
                d2 = d.date()
                max_obs = d2 if max_obs is None else max(max_obs, d2)
        except Exception:
            pass

        canon.to_csv(out_path, mode="a", header=not wrote_header, index=False)
        wrote_header = True

        manifest_by_id[str(r.id)] = {
            "id": r.id,
            "name": r.name,
            "url": r.url,
            "format": r.fmt,
            "last_modified": r.last_modified,
            "year": r.year,
            "month": r.month,
            "rows": int(len(canon)),
        }

        # Persist incrementally so interrupted runs keep progress.
        try:
            merged = sorted(
                manifest_by_id.values(),
                key=lambda x: (
                    int(x.get("year") or 9999),
                    int(x.get("month") or 99),
                    str(x.get("name") or ""),
                ),
            )
            manifest_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        except Exception:
            pass

    if not wrote_header:
        raise RuntimeError("No rows written")

    # Update fetch state
    if max_obs is not None:
        state: dict[str, str] = {}
        if FETCH_STATE_JSON.exists():
            try:
                state = json.loads(FETCH_STATE_JSON.read_text(encoding="utf-8"))
            except Exception:
                state = {}
        state["au_nsw_fuelcheck_history"] = max_obs.isoformat()
        FETCH_STATE_JSON.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # Ensure final manifest is present (may already be written incrementally).
    if not manifest_path.exists():
        merged = sorted(
            manifest_by_id.values(),
            key=lambda x: (
                int(x.get("year") or 9999),
                int(x.get("month") or 99),
                str(x.get("name") or ""),
            ),
        )
        manifest_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return out_path
