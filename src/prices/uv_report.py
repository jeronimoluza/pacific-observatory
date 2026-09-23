"""Why each unit-value-flagged build row failed: a guessed cause per row, a share per source.

Build step 2 of the operating model (vault spec
`2026-09-23-prices-ai-operating-model`, Q23). It reads the build's `qa_status`
and never changes it: the plausibility band, k=5.0, the minimum support and the
support window are out of scope here.

Each flagged row (review_uv_outlier or review_uv_implausible) is compared with a
trusted reference for its leaf and unit, and the ratio's size names the defect:

- `scale_1000`       ~10^3 off on a mass/volume row: g read as kg, ml as l, or
                     a decimal price read x1000 ("130.150" as 130150)
- `scale_100`        ~10^2 off: cents read as units, or a per-kg price stored
                     with a 100 kg (quintal) quantity
- `currency`         FX rate of 1 in a country whose FX is not ~1 (a USD price
                     stored as local), off by the country's FX rate where that
                     rate is large and clear of 10^2 and 10^3, or FX already
                     marked suspect
- `pack_count`       off by an integer N that appears in the product name
                     (6x330 ml priced as one 330 ml can, or the reverse)
- `per_100g`         5x or more below, the price is ~0.1 of the per-kg/l
                     reference, and the row is sold by weight (amount 1) or
                     names 100 g/ml: a per-100 g price, or a per-piece price,
                     read as the pack price
- `near_reference`   within 3x of the reference: no extraction signature,
                     the band or the cell is the likelier cause
- `off_3_10x`        3-10x off with no signature: wholesale against a retail
                     reference, premium goods, or misclassification
- `off_over_10x`     more than 10x off with no signature: the rows to read
- `no_reference`     no trusted row shares its leaf and unit

References are medians over `trusted` rows: local unit value per (leaf,
country, unit), USD unit value per (leaf, unit) across countries, and FX rate
per country. Trusted rows carrying an FX rate of 1 in a country whose FX is not
~1 are left out of the unit-value references: they are USD prices stored as
local (livingcost, waltermart), and in thin cells they had become the median
(Japan panko at 3.29 JPY/kg). An outlier is judged against its country; an implausible row against its country
when it stands out there (3x or more), otherwise against the global reference,
because an implausible row that looks normal locally means the whole country
cell is shifted. Signatures are guesses; the spot check is what trusts them.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import click
import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq

from prices.gate import BUILD_PARQUET, REPO_ROOT

FLAGGED = ("review_uv_outlier", "review_uv_implausible")
OUT_DIR = REPO_ROOT / "outputs" / "prices"
ROWS_PARQUET = OUT_DIR / "uv_failure_rows.parquet"
SOURCES_PARQUET = OUT_DIR / "uv_failure_sources.parquet"
CAUSES = (
    "scale_1000",
    "scale_100",
    "currency",
    "pack_count",
    "per_100g",
    "near_reference",
    "off_3_10x",
    "off_over_10x",
    "no_reference",
)

TOL = 0.25  # log10 tolerance for the 10^3, 10^2 and FX signatures (x1.8)
FX_MIN = 2.0  # below 10^2 an FX-sized gap is indistinguishable from ordinary scatter
PACK_TOL = 0.06  # x1.15 for N < 6, where a small integer can match by chance
# N >= 6 gets TOL: a big pack is rarely a coincidence, and a pack of small units
# costs more per kg than the reference, so "48 x 36 g" misses x48 by x1.6.
PER100_TOL = 0.15  # x1.4
NEAR = np.log10(3)

# Integers 2..99 in a name that are not themselves a quantity ("330ml", "1.5 kg")
# or an age, a duration or a variety count (21年, 14 YO, 7日分, 38種類).
_PACK_N = re.compile(
    r"(?<![\d.,])(\d{1,2})(?![\d.,])"
    r"(?!\s*(?:k?g|mg|gr|grams?|m?l|cl|dl|lt?r?s?|litres?|liters?|gms?|oz|lbs?|%|\+|y|yo|yrs?|years?|кг|гр?|мл|л|γρ|年|日|人|種|度)(?![a-zа-я]))",
    re.I,
)
_PER100 = re.compile(r"100\s*(?:g|gr|ml)(?![a-z])", re.I)


def _refs(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    t = pq.read_table(
        path,
        columns=["coicop_code", "country", "standard_unit", "unit_value_local", "unit_value_usd", "fx_rate"],
        filters=pc.field("qa_status") == "trusted",
    )
    fx = (
        t.group_by("country")
        .aggregate([("fx_rate", "approximate_median")])
        .rename_columns(["country", "country_fx"])
        .to_pandas()
    )
    far = fx.loc[np.abs(np.log10(fx["country_fx"])) >= 0.5, "country"].tolist()
    t = t.filter(~(pc.field("country").isin(far) & (pc.field("fx_rate") == 1.0)))
    local = (
        t.group_by(["coicop_code", "country", "standard_unit"])
        .aggregate([("unit_value_local", "approximate_median")])
        .rename_columns(["coicop_code", "country", "standard_unit", "ref_local"])
        .to_pandas()
    )
    glob = (
        t.group_by(["coicop_code", "standard_unit"])
        .aggregate([("unit_value_usd", "approximate_median")])
        .rename_columns(["coicop_code", "standard_unit", "ref_usd"])
        .to_pandas()
    )
    return local, glob, fx


def _pack_ns(name) -> list[int]:
    if not isinstance(name, str):
        return []
    return [n for n in map(int, _PACK_N.findall(unicodedata.normalize("NFKC", name))) if n >= 2]


def guess_causes(rows: pd.DataFrame) -> pd.DataFrame:
    """Add `ref_kind`, `log10_ratio` and `cause` to flagged rows carrying ref_local/ref_usd/country_fx."""
    lr_loc = np.log10(rows["unit_value_local"] / rows["ref_local"])
    lr_glob = np.log10(rows["unit_value_usd"] / rows["ref_usd"])
    use_local = lr_loc.notna() & (
        (rows["qa_status"] == "review_uv_outlier") | (lr_loc.abs() >= NEAR)
    )
    rows = rows.assign(
        ref_kind=np.where(use_local, "local", np.where(lr_glob.notna(), "global", "none")),
        log10_ratio=np.where(use_local, lr_loc, lr_glob),
    )
    # the expected per-100 g price, in the same currency as the reference used
    ref_price = np.where(use_local, rows["ref_local"], rows["ref_usd"]) * 0.1
    price = np.where(use_local, rows["price_local"], rows["price_usd"])
    measured = rows["pricing_basis"].isin(["mass", "volume"]).to_numpy()
    by_weight = np.isclose(rows["amount_value"].to_numpy(), 1.0)
    names_100 = rows["product_name"].str.contains(_PER100, na=False).to_numpy()

    lr = rows["log10_ratio"].to_numpy()
    fx = np.log10(rows["country_fx"].to_numpy())
    fx_is_one = np.isclose(rows["fx_rate"].to_numpy(), 1.0) & (np.abs(fx) >= 0.5)
    fx_clear = (
        (np.abs(fx) >= FX_MIN) & (np.abs(np.abs(fx) - 2) >= TOL) & (np.abs(np.abs(fx) - 3) >= TOL)
    )
    # distance to each signature, scaled by its tolerance; the nearest under 1 wins
    score = {
        "scale_1000": np.where(measured, np.abs(np.abs(lr) - 3), np.inf) / TOL,
        "scale_100": np.abs(np.abs(lr) - 2) / TOL,
        "currency": np.where(fx_clear, np.abs(np.abs(lr) - np.abs(fx)), np.inf) / TOL,
        "per_100g": np.where(
            measured & (lr <= -np.log10(5)) & (by_weight | names_100),
            np.abs(np.log10(price / ref_price)),
            np.inf,
        )
        / PER100_TOL,
    }
    pack = np.full(len(rows), np.inf)
    for i, (name, r) in enumerate(zip(rows["product_name"], np.abs(lr))):
        ns = _pack_ns(name)
        if ns and np.isfinite(r):
            pack[i] = min(abs(r - np.log10(n)) / (TOL if n >= 6 else PACK_TOL) for n in ns)
    score["pack_count"] = pack

    names = list(score)
    stack = np.nan_to_num(np.vstack([score[k] for k in names]), nan=np.inf)
    best = stack.argmin(axis=0)
    hit = stack.min(axis=0) < 1
    cause = np.where(hit, np.array(names)[best], "")
    cause = np.where(~hit & rows["fx_suspect"].fillna(False).to_numpy(), "currency", cause)
    cause = np.where(
        cause == "",
        np.select([np.abs(lr) < NEAR, np.abs(lr) <= 1], ["near_reference", "off_3_10x"], "off_over_10x"),
        cause,
    )
    cause = np.where(np.isnan(lr), "no_reference", cause)
    cause = np.where(fx_is_one, "currency", cause)
    return rows.assign(cause=cause)


def build_report(path: Path = BUILD_PARQUET) -> tuple[pd.DataFrame, pd.DataFrame]:
    local, glob, fx = _refs(path)
    rows = pq.read_table(
        path,
        columns=[
            "product_name", "product_url", "country", "source", "coicop_code",
            "pricing_basis", "amount_value", "standard_unit", "count", "multiplier",
            "price_local", "unit_value_local", "fx_rate", "fx_suspect", "price_usd",
            "unit_value_usd", "uv_robust_z", "qa_status",
        ],
        filters=pc.field("qa_status").isin(list(FLAGGED)),
    ).to_pandas()
    rows = rows.merge(local, on=["coicop_code", "country", "standard_unit"], how="left")
    rows = rows.merge(glob, on=["coicop_code", "standard_unit"], how="left")
    rows = rows.merge(fx, on="country", how="left")
    rows = guess_causes(rows)

    totals = (
        pq.read_table(path, columns=["country", "source"])
        .group_by(["country", "source"])
        .aggregate([("source", "count")])
        .rename_columns(["country", "source", "n_rows"])
        .to_pandas()
    )
    by_status = rows.pivot_table(
        index=["country", "source"], columns="qa_status", aggfunc="size", fill_value=0
    ).rename(columns={"review_uv_outlier": "n_outlier", "review_uv_implausible": "n_implausible"})
    by_cause = rows.pivot_table(
        index=["country", "source"], columns="cause", aggfunc="size", fill_value=0
    ).reindex(columns=list(CAUSES), fill_value=0)
    sources = totals.merge(
        by_status.join(by_cause).reset_index(), on=["country", "source"], how="left"
    ).fillna(0)
    counts = sources[["n_outlier", "n_implausible", *CAUSES]].astype("int64")
    sources[counts.columns] = counts
    sources["n_flagged"] = sources["n_outlier"] + sources["n_implausible"]
    sources["flagged_share"] = sources["n_flagged"] / sources["n_rows"]
    sources["top_cause"] = np.where(sources["n_flagged"] > 0, counts[list(CAUSES)].idxmax(axis=1), "")
    return rows, sources.sort_values("n_flagged", ascending=False, ignore_index=True)


@click.command("uv-report")
def uv_report() -> None:
    """Guess a cause for every unit-value-flagged build row; write per-row and per-source tables."""
    rows, sources = build_report()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows.to_parquet(ROWS_PARQUET, index=False)
    sources.to_parquet(SOURCES_PARQUET, index=False)
    click.echo(rows.groupby(["qa_status", "cause"]).size().unstack(0, fill_value=0).to_string())
    click.echo(f"\n{len(rows):,} flagged rows over {int((sources['n_flagged'] > 0).sum()):,} sources")
    cols = ["country", "source", "n_rows", "n_flagged", "flagged_share", "top_cause"]
    click.echo(sources[cols].head(25).to_string(index=False))
    click.echo(f"\nwrote {ROWS_PARQUET}\nwrote {SOURCES_PARQUET}")
