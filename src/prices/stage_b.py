"""Stage B for one country: 01 + 02.1 extraction, basis check, band, trust.

Spec: vault `specs/prices-refactor/stage-b-extraction.md` and `stage-b-trust.md`.

Pilot input. Stage B starts from Stage A rows (price rows plus one COICOP per
product). Until Stage A writes those on its own, the pilot reads them from the
precision-sweep build (`data/prices/build/global_prices_observations.parquet`,
2026-09-15), which is exactly that population: the frozen classifier's
accepted 01 + 02.1 rows, joined to their prices and FX. Its quantity and trust
columns are kept as `base_*` for the comparison and never read otherwise.

Rows are re-keyed to `input_hash` through `products_input` on
(product_name, product_url), never by recomputing the hash: the build predates
the source fold, so recomputing with this branch's key would miss every row.

Extraction runs only on this country's 01 + 02.1 products and is not cached:
Vietnam is ~54k products and seconds of regex, so the extraction-cache
freshness items do not arise here.

Writes `outputs/prices/stage_b/<country>/`, which in a refactor worktree is
outside the production tree.
"""

from __future__ import annotations

import click
import numpy as np
import pandas as pd
import pyarrow.dataset as pads

from prices.build import trust
from prices.build.aggregate import OBSERVATIONS_PARQUET
from prices.build.qa import PLAUSIBLE_USD
from prices.build.unit_value_audit import flag_uv_outliers
from prices.enrich import config, uv_gate
from prices.enrich.fluid_oz import remap_fluid_oz
from prices.enrich.stages import decisions_store
from prices.enrich.stages.extraction import EXTRACTION_FIELDS, extract_frame
from prices.enrich.source_canonical import canonical_source
from prices.enrich.stages.merge import compute_unit_value
from prices.enrich.stages.prepare import _clean_url
from prices.enrich.versioning import input_hash

DIVISIONS = ("01.", "02.1.")
OUT_ROOT = config.REPO_ROOT / "outputs" / "prices" / "stage_b"

_OBS_COLS = [
    "product_name", "product_url", "currency", "country", "source",
    "observation_date", "coicop_code", "confidence", "price_local",
    "fx_rate", "fx_rate_date", "fx_suspect",
]
_BASE_COLS = [
    "pricing_basis", "amount_value", "standard_unit", "count", "multiplier",
    "mass_source", "unit_value_local", "uv_robust_z", "qa_status",
]
_PRODUCT_COLS = [
    "input_hash", "product_name_original", "product_url", "category",
    "details", "unit", "lang", "source", "country",
]


def _in_divisions(codes: pd.Series) -> pd.Series:
    return codes.fillna("").str.startswith(DIVISIONS)


def load_rows(country: str) -> pd.DataFrame:
    """Stage A rows for `country`, 01 + 02.1, keyed by `input_hash`."""
    obs = (
        pads.dataset(OBSERVATIONS_PARQUET)
        .to_table(columns=_OBS_COLS + _BASE_COLS, filter=pads.field("country") == country)
        .to_pandas()
    )
    obs = obs[_in_divisions(obs["coicop_code"])].reset_index(drop=True)
    obs = obs.rename(columns={c: f"base_{c}" for c in _BASE_COLS})

    products = (
        pads.dataset(config.PRODUCTS_INPUT_PARQUET)
        .to_table(columns=_PRODUCT_COLS, filter=pads.field("country") == country)
        .to_pandas()
    )
    # products_input is post-fold: a product is (source, name, url).
    products["_src"] = products["source"].map(canonical_source)
    obs["_src"] = obs["source"].map(canonical_source)
    key = ["product_name_original", "product_url", "_src"]
    if products.duplicated(key).any():
        raise RuntimeError(f"{country}: products_input repeats a (source, name, url) key")
    rows = obs.merge(
        products[key + ["input_hash"]],
        left_on=["product_name", "product_url", "_src"], right_on=key, how="left",
    ).drop(columns=["product_name_original"])
    if rows["input_hash"].isna().any():
        raise RuntimeError(f"{country}: {rows['input_hash'].isna().sum()} rows have no input_hash")

    # Grain check: the COICOP Stage A wrote must be the one the rows carry.
    # classified_hierlex predates the fold, so it is keyed on the pre-fold hash.
    part = decisions_store.parts_root(config.CLASSIFIED_HIERLEX_PARQUET) / (
        decisions_store.part_name(country) + ".parquet"
    )
    classified = pd.read_parquet(part, columns=["input_hash", "coicop_code"])
    if classified["input_hash"].duplicated().any():
        raise RuntimeError(f"{part}: duplicate input_hash")
    pre_fold = [
        input_hash({"product_name_original": str(n), "product_url": _clean_url(u)})
        for n, u in zip(rows["product_name"], rows["product_url"])
    ]
    check = pd.DataFrame({"input_hash": pre_fold, "coicop_code": rows["coicop_code"]}).merge(
        classified, on="input_hash", how="left", suffixes=("", "_a")
    )
    bad = (check["coicop_code"] != check["coicop_code_a"]).sum()
    if bad:
        raise RuntimeError(f"{country}: {bad} rows disagree with Stage A COICOP")
    rows = rows.drop(columns=["_src", "product_url_y"], errors="ignore")
    return rows, products[products["input_hash"].isin(rows["input_hash"])]


def extract_products(products: pd.DataFrame, codes: pd.DataFrame) -> pd.DataFrame:
    """Extraction on 01 + 02.1 products, then reconcile: fluid-oz remap ->
    basis check (in `run`) -> uv_gate. The remap must come first: the basis
    check would otherwise rule on a basis it is about to replace."""
    ex = extract_frame(products)
    if ex.duplicated(["input_hash", "country"]).any():
        raise RuntimeError("extraction repeats an (input_hash, country) key")
    ex = ex.merge(codes, on="input_hash", how="left")
    names = products.set_index("input_hash")["product_name_original"]
    recs = ex.to_dict("records")
    for rec in recs:
        remap_fluid_oz(rec, str(names[rec["input_hash"]]))
    ex = pd.DataFrame(recs, columns=ex.columns)
    for col in ("amount_value", "count", "multiplier"):
        ex[col] = pd.to_numeric(ex[col], errors="coerce").astype("float64")
    ex["qa_uv_category"] = [
        uv_gate.gate(c, b)[0] for c, b in zip(ex["coicop_code"], ex["pricing_basis"])
    ]
    return ex[["input_hash", *EXTRACTION_FIELDS, "qa_uv_category"]]


def _status(df: pd.DataFrame) -> np.ndarray:
    level, src = df["qa_level"], df["size_source"]
    conditions = [
        ~df["qa_price_positive"],
        df["basis_mismatch"],
        src.isna(),
        df["piece_fail"],
        ~df["qa_uv_category"],
        level.eq("unscored"),
        level.eq("out"),
        src.eq("imputed_fit") | (src.isin(["imputed_mode", "per_kg"]) & level.eq("C")),
        ~df["qa_uv_plausible"],
        ~df["qa_fx"],
    ]
    choices = [
        "review_zero_price", "review_basis", "review_missing_qty",
        "review_piece", "review_uv_category", "review_uv_unscored", "review_uv_out",
        "review_level", "review_uv_implausible", "review_fx",
    ]
    return np.select(conditions, choices, default="trusted").astype(object)


def run(country: str) -> pd.DataFrame:
    rows, products = load_rows(country)
    codes = rows[["input_hash", "coicop_code"]].drop_duplicates("input_hash")
    ex = extract_products(products, codes)
    n = len(rows)
    rows = rows.merge(ex, on="input_hash", how="left")
    if len(rows) != n:
        raise RuntimeError("extraction join changed the row count")
    rows["_row"] = np.arange(n)

    allowed = trust.allowed_bases(country)
    missing = sorted(set(rows["coicop_code"]) - set(allowed))
    if missing:
        raise RuntimeError(f"leaves missing from the basis map: {missing}")
    basis = rows["pricing_basis"]
    rows["basis_ok"] = [b in allowed[c] for b, c in zip(basis, rows["coicop_code"])]
    sizeless = ~rows["basis_ok"] & (basis.isna() | basis.eq("item"))
    # An allowed item row is one piece, the same quantity as a count of one:
    # both price per piece, so they share the count cell ("Thơm 1 trái" and
    # "Thơm" are one pineapple each) instead of thinning two cells.
    rows.loc[rows["basis_ok"] & basis.eq("item"), "standard_unit"] = "unit"
    rows["basis_mismatch"] = ~rows["basis_ok"] & ~sizeless
    rows["qa_price_positive"] = pd.to_numeric(rows["price_local"], errors="coerce").gt(0)
    rows["unit_value_local"] = pd.to_numeric(pd.Series([
        compute_unit_value(p, b, a, c, m)
        for p, b, a, c, m in zip(
            rows["price_local"], basis, rows["amount_value"], rows["count"], rows["multiplier"]
        )
    ], index=rows.index, dtype=object), errors="coerce")
    rows["size_qty"] = [
        trust.size_of(*t)[1]
        for t in zip(basis, rows["amount_value"], rows["count"], rows["multiplier"])
    ]
    rows["size_source"] = pd.Series(np.where(rows["basis_ok"], "extracted", None), dtype=object)

    # Per-piece rows from a shop whose own per-kg price says they are not
    # pieces (bags, bulk packs) leave before the band and are never imputed.
    pieces = piece_table(rows[rows["basis_ok"]])
    failed = set(pieces.index[pieces["outside"] & pieces["ref"].eq("same source")])
    rows["piece_fail"] = basis.eq("item") & pd.Series(
        [k in failed for k in zip(rows["coicop_code"], rows["source"])], index=rows.index
    )

    # The band: extracted rows in an allowed basis define it, twice over.
    is_ex = rows["basis_ok"] & rows["qa_price_positive"] & rows["unit_value_local"].gt(0) & ~rows["piece_fail"]
    extracted = rows[is_ex].reset_index(drop=True)
    base2 = trust.band(extracted, pd.Series(True, index=extracted.index))

    # Imputation draws sizes from in-band measured rows of the same country.
    pool = extracted[base2 & extracted["pricing_basis"].isin(["mass", "volume", "count"])]
    # A shop that sells the leaf per kg at the same price is quoting per kg.
    todo = rows[sizeless & rows["qa_price_positive"]]
    perkg = trust.per_kg_rows(extracted, todo)
    cand = trust.impute_candidates(pool, todo[~todo["_row"].isin(perkg["_row"])])

    both = pd.concat([extracted, perkg, cand], ignore_index=True)
    mask = pd.Series(np.r_[base2.to_numpy(), np.zeros(len(perkg) + len(cand), bool)], index=both.index)
    scored = flag_uv_outliers(both, group_cols=tuple(trust.CELL), baseline_mask=mask, k=trust.K)
    ne, npk = len(extracted), len(perkg)
    chosen = pd.concat(
        [scored.iloc[ne : ne + npk], trust.choose_fit(scored.iloc[ne + npk :].reset_index(drop=True))],
        ignore_index=True,
    )
    if chosen["_row"].duplicated().any():
        raise RuntimeError("imputation kept two sizes for one row")

    judged = pd.concat(
        [scored.iloc[:ne], chosen.drop(columns=["_cand_share"], errors="ignore")], ignore_index=True
    )
    judged_base = pd.Series(np.r_[base2.to_numpy(), np.zeros(len(chosen), bool)], index=judged.index)
    judged["in_band_baseline"] = judged_base
    judged["cell_sources"] = trust.cell_sources(judged, judged_base)
    judged["qa_level"] = trust.qa_level(judged["uv_robust_z"], judged["cell_sources"])

    rest = rows[~rows["_row"].isin(judged["_row"])].assign(
        qa_level="unscored", in_band_baseline=False
    )
    rest.loc[~rest["basis_ok"], "size_source"] = None
    out = pd.concat([judged, rest], ignore_index=True).sort_values("_row", ignore_index=True)
    if len(out) != n or out["_row"].duplicated().any():
        raise RuntimeError(f"row count moved: {n} in, {len(out)} out")

    out["unit_value_usd"] = out["unit_value_local"] / pd.to_numeric(out["fx_rate"], errors="coerce")
    lo = pd.to_numeric(out["standard_unit"].map(lambda u: PLAUSIBLE_USD.get(u, (None, None))[0]))
    hi = pd.to_numeric(out["standard_unit"].map(lambda u: PLAUSIBLE_USD.get(u, (None, None))[1]))
    uv = out["unit_value_usd"]
    out["qa_uv_plausible"] = lo.isna() | uv.isna() | uv.between(lo, hi)
    out["qa_fx"] = out["fx_rate"].notna() & ~out["fx_suspect"].fillna(False).astype(bool)
    out["qa_uv_category"] = out["qa_uv_category"].fillna(True).astype(bool)
    out["stage_b_status"] = _status(out)
    out["trusted"] = out["stage_b_status"].eq("trusted")
    return out.drop(columns=["_row", "_cand", "_cand_share"], errors="ignore")


# Human-owned, like k=5: how far an implied piece weight may sit from the
# leaf's `piece_kg` range before the "pieces" are judged not to be pieces.
PIECE_BOUNDS = (0.4, 2.5)


def piece_table(rows: pd.DataFrame) -> pd.DataFrame:
    """Implied piece weight per (leaf, source) for leaves that allow `item`.

    Implied weight = median per-piece price / median per-kg price, from the
    same source when it has >= 3 per-kg rows of the leaf, else the country's.
    `outside` marks weights beyond PIECE_BOUNDS x the leaf's `piece_kg`.
    Only a same-source comparison is trusted to exclude rows (`run`): against
    the country's price, a premium shop reads as heavy pieces.
    """
    m = pd.read_csv(trust.BASIS_MAP_CSV, dtype=str, keep_default_na=False)
    rng = m[m["piece_kg"].ne("")].set_index("code")["piece_kg"].str.split("-", expand=True).astype(float)
    rows = rows[rows["coicop_code"].isin(rng.index) & rows["unit_value_local"].gt(0)]
    kg = rows[rows["pricing_basis"].eq("mass")]
    own = kg.groupby(["coicop_code", "source"])["unit_value_local"].agg(["size", "median"])
    country = kg.groupby("coicop_code")["unit_value_local"].median()
    it = rows[rows["pricing_basis"].eq("item")].groupby(["coicop_code", "source"])["unit_value_local"].agg(["size", "median"])
    it = it[it["size"] >= 3]
    leaf = it.index.get_level_values(0)
    ref = own["median"].where(own["size"] >= 3).reindex(it.index)
    it["ref"] = np.where(ref.notna(), "same source", "country")
    it["implied_kg"] = (it["median"] / ref.fillna(pd.Series(leaf.map(country), index=it.index))).round(2)
    it["piece_kg"] = leaf.map(m.set_index("code")["piece_kg"])
    lo, hi = leaf.map(rng[0]), leaf.map(rng[1])
    it["outside"] = (it["implied_kg"] < PIECE_BOUNDS[0] * lo) | (it["implied_kg"] > PIECE_BOUNDS[1] * hi)
    return it


def report(out: pd.DataFrame) -> str:
    """Counts against the precision-sweep build, same rows, same COICOP."""
    lines = [f"rows {len(out):,}  products {out['input_hash'].nunique():,}"]
    t = out[out["trusted"]]
    lines.append(f"trusted now {len(t):,}  before {out['base_qa_status'].eq('trusted').sum():,}")
    lines.append("\ntrusted by qa_level x size_source")
    lines.append(pd.crosstab(t["qa_level"], t["size_source"], margins=True).to_string())
    lines.append("\nall rows by stage_b_status x size_source")
    lines.append(pd.crosstab(out["stage_b_status"], out["size_source"].fillna("none"), margins=True).to_string())
    before = out["base_qa_status"].eq("trusted")
    lines.append("\nlost (trusted before, not now) by new status")
    lines.append(out.loc[before & ~out["trusted"], "stage_b_status"].value_counts().to_string())
    lines.append("\ngained (trusted now, not before) by old status")
    lines.append(out.loc[~before & out["trusted"], "base_qa_status"].value_counts().to_string())
    lines.append("\nbasis disagreement: leaves whose extracted rows mostly sit outside the map")
    sized = out[out["pricing_basis"].notna() & out["pricing_basis"].ne("item")]
    g = sized.groupby("coicop_code").agg(rows=("basis_ok", "size"), in_map=("basis_ok", "mean"))
    lines.append(g[(g["rows"] >= 30) & (g["in_map"] < 0.5)].sort_values("rows", ascending=False).to_string())
    ab = out["qa_level"].isin(["A", "B"])
    share = ab.groupby(out["source"]).mean()
    lines.append(f"\nA+B share by source (country {ab.mean():.1%}; patch-agent trigger >= 10 points below)")
    lines.append(pd.DataFrame({"rows": out["source"].value_counts(), "ab_share": share}).sort_values("rows", ascending=False).to_string())
    outs = out["qa_level"].eq("out").groupby(out["coicop_code"]).agg(["size", "mean"])
    lines.append("\nleaves with out share > 5% (review-agent trigger)")
    lines.append(outs[(outs["mean"] > 0.05) & (outs["size"] >= 30)].sort_values("size", ascending=False).to_string())
    lines.append("\nimplied piece weight outside PIECE_BOUNDS x piece_kg (same source: excluded as review_piece; country: review only)")
    lines.append(piece_table(out[out["size_source"].eq("extracted")]).query("outside").to_string())
    return "\n".join(lines)


_SAMPLE_COLS = [
    "source", "product_name", "coicop_code", "price_local", "pricing_basis",
    "amount_value", "count", "multiplier", "standard_unit", "unit_value_local",
    "unit_value_usd", "size_source", "qa_level", "uv_robust_z", "stage_b_status",
]


def write(country: str, out: pd.DataFrame) -> None:
    root = OUT_ROOT / decisions_store.part_name(country)
    root.mkdir(parents=True, exist_ok=True)
    out.to_parquet(root / "observations.parquet", index=False)
    out[out["trusted"]].to_parquet(root / "trusted_observations.parquet", index=False)
    (root / "report.txt").write_text(report(out))
    # Hand-check samples (spec evaluation step 2): 100 A/B rows, 50 imputed.
    ab = out[out["trusted"] & out["qa_level"].isin(["A", "B"])]
    ab.sample(min(100, len(ab)), random_state=0)[_SAMPLE_COLS].to_csv(root / "check_ab.csv", index=False)
    imp = out[out["size_source"].isin(["imputed_mode", "imputed_fit"])]
    imp.sample(min(50, len(imp)), random_state=0)[_SAMPLE_COLS].to_csv(root / "check_imputed.csv", index=False)


@click.command("stage-b")
@click.option("--country", required=True, help="Country slug, e.g. vietnam.")
def stage_b(country: str) -> None:
    """Stage B for one country: 01 + 02.1 extraction, basis map, band, trust."""
    out = run(country)
    write(country, out)
    click.echo(report(out))
    click.echo(f"\nwrote {OUT_ROOT / decisions_store.part_name(country)}")
