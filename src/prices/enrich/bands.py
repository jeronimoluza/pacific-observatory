import glob
import json
from datetime import datetime, timezone
from pathlib import Path

import click
import pandas as pd

from prices.enrich import config
from prices.enrich.base_items.promote import _band

LEAF_PRICE_BANDS_PATH = config.ENRICH_DIR / "leaf_price_bands.parquet"
BANDS_MANIFEST_PATH = config.ENRICH_DIR / "leaf_price_bands_manifest.json"
GREEN_GLOB = str(config.ENRICH_DIR / "validation_runs" / "*" / "latest" / "green.csv")

MIN_BAND_N = 5


def _load_green() -> pd.DataFrame:
    frames = []
    for f in sorted(glob.glob(GREEN_GLOB)):
        try:
            g = pd.read_csv(f)
        except Exception:
            continue
        if g.empty:
            continue
        need = {"coicop_deep_leaf_code", "country", "pricing_basis", "unit_value_usd"}
        if not need.issubset(g.columns):
            continue
        frames.append(g[list(need)])
    if not frames:
        return pd.DataFrame(
            columns=[
                "coicop_deep_leaf_code",
                "country",
                "pricing_basis",
                "unit_value_usd",
            ]
        )
    return pd.concat(frames, ignore_index=True)


def build_price_bands(path=LEAF_PRICE_BANDS_PATH) -> pd.DataFrame:
    g = _load_green()
    g = g.dropna(
        subset=["coicop_deep_leaf_code", "country", "pricing_basis", "unit_value_usd"]
    )
    g["unit_value_usd"] = pd.to_numeric(g["unit_value_usd"], errors="coerce")
    g = g[g["unit_value_usd"].notna() & (g["unit_value_usd"] > 0)]

    rows = []
    computed_at = datetime.now(timezone.utc).isoformat()
    for (leaf, country, basis), grp in g.groupby(
        ["coicop_deep_leaf_code", "country", "pricing_basis"]
    ):
        vals = grp["unit_value_usd"].to_numpy(dtype=float)
        if len(vals) < MIN_BAND_N:
            continue
        m, lo, hi = _band(vals)
        rows.append(
            {
                "leaf": leaf,
                "country": country,
                "pricing_basis": basis,
                "n": int(len(vals)),
                "median_usd": float(m),
                "band_lo": float(lo),
                "band_hi": float(hi),
                "computed_at": computed_at,
            }
        )

    bands = pd.DataFrame(
        rows,
        columns=[
            "leaf",
            "country",
            "pricing_basis",
            "n",
            "median_usd",
            "band_lo",
            "band_hi",
            "computed_at",
        ],
    )
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    bands.to_parquet(p, index=False)

    manifest = {
        "created_at": computed_at,
        "params": {"min_band_n": MIN_BAND_N, "k_mad": 3.0},
        "inputs": {"green_glob": GREEN_GLOB, "green_rows": int(len(g))},
        "n_bands": int(len(bands)),
    }
    BANDS_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return bands


def load_price_bands(path=LEAF_PRICE_BANDS_PATH) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(
            columns=[
                "leaf",
                "country",
                "pricing_basis",
                "n",
                "median_usd",
                "band_lo",
                "band_hi",
                "computed_at",
            ]
        )
    return pd.read_parquet(p)


@click.command("build-price-bands")
def build_price_bands_command():
    """Export leaf-grain price bands (median +/- 3*MAD) from earned GREEN observations."""
    bands = build_price_bands()
    click.echo(
        f"price bands: {len(bands)} (leaf,country,basis) groups -> {LEAF_PRICE_BANDS_PATH}"
    )
    if not bands.empty:
        click.echo(
            f"  leaves covered: {bands['leaf'].nunique()}, countries: {bands['country'].nunique()}"
        )
