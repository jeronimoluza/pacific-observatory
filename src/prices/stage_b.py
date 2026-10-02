"""Stage B for one country: 01 + 02.1 extraction, basis check, band, trust.

Spec: vault `specs/prices-refactor/stage-b-extraction.md` and `stage-b-trust.md`
(Grain section).

Reads Stage A only: classify's `classified` part for the country (one COICOP
per `input_hash`), `products_input` (the product's text, for extraction) and
prepare's `product_months` (median price per product and month). A size is a
property of the product and is decided once per product; a check on a price is
judged per product-month. Dated observation rows are joined back only at the
end, right before publish: each takes its product-month's verdict, and a row
priced outside RATIO_BOUNDS of its product-month median is flagged.

Extraction runs only on this country's 01 + 02.1 products and is not cached.

Writes `outputs/prices/stage_b/<country>/`, which in a refactor worktree is
outside the production tree.
"""

from __future__ import annotations

import click
import numpy as np
import pandas as pd
import pyarrow.dataset as pads
import pyarrow.parquet as pq

from prices import partition
from prices.build import trust
from prices.build.qa import PLAUSIBLE_USD
from prices.build.unit_value_audit import flag_uv_outliers
from prices.enrich import config, uv_gate
from prices.enrich.fluid_oz import remap_fluid_oz
from prices.enrich.prepare_shards import PRODUCT_MONTHS_DIR
from prices.enrich.stages import decisions_store
from prices.enrich.stages.concatenate import PER_SOURCE_DIR
from prices.enrich.stages.extraction import EXTRACTION_FIELDS, extract_frame
from prices.enrich.stages.merge import compute_unit_value
from prices.enrich.stages.prepare import month_of, parse_dates, parse_price
from prices.fx import attach as fx

DIVISIONS = ("01.", "02.1.")
OUT_ROOT = config.REPO_ROOT / "outputs" / "prices" / "stage_b"

# Human-owned, like k=5: a dated row priced outside this factor of its
# product-month median does not inherit the product-month's trust.
RATIO_BOUNDS = (0.5, 2.0)
# Human-owned: an official series (`official_sources.csv`) is judged against
# its own history instead. A product-month outside this factor of the
# product's median over its months, or a dated row outside it of its
# product-month median, is out.
OFFICIAL_BOUNDS = (0.2, 5.0)

_PRODUCT_COLS = [
    "input_hash", "product_name_original", "product_url", "category",
    "details", "unit", "lang", "source", "country", "currency",
]
_DATED_COLS = ["input_hash", "product_name", "product_url", "price", "currency", "date", "source"]


def _in_divisions(codes: pd.Series) -> pd.Series:
    return codes.fillna("").str.startswith(DIVISIONS)


def load_products(country: str) -> pd.DataFrame:
    """This country's 01 + 02.1 products: classify's COICOP joined to the
    product text extraction reads. One row per `input_hash`."""
    part = decisions_store.parts_root(config.CLASSIFIED_HIERLEX_PARQUET) / (
        decisions_store.part_name(country) + ".parquet"
    )
    classified = pd.read_parquet(part, columns=["input_hash", "coicop_code", "state"])
    classified = classified[_in_divisions(classified["coicop_code"])]
    if classified["input_hash"].duplicated().any():
        raise RuntimeError(f"{part}: duplicate input_hash")
    products = (
        pads.dataset(config.PRODUCTS_INPUT_PARQUET)
        .to_table(columns=_PRODUCT_COLS, filter=pads.field("country") == country)
        .to_pandas()
    )
    products = products.merge(classified, on="input_hash", how="inner", validate="one_to_one")
    if len(products) != len(classified):
        raise RuntimeError(
            f"{country}: {len(classified) - len(products)} classified products "
            "are not in products_input"
        )
    # Human-approved leaf corrections (`coicop_overrides.csv`); one that moves a
    # product out of 01 + 02.1 drops it here.
    over = trust.coicop_overrides()
    fixed = pd.Series(list(zip(products["source"], products["product_name_original"])), index=products.index).map(over)
    products["coicop_code"] = fixed.fillna(products["coicop_code"])
    return products[_in_divisions(products["coicop_code"])].reset_index(drop=True)


def load_months(country: str, hashes: pd.Series) -> pd.DataFrame:
    """prepare's `product_months` for `hashes`: one row per (product, month)."""
    paths = sorted(PRODUCT_MONTHS_DIR.rglob(f"{country}.parquet"))
    if len(paths) != 1:
        raise RuntimeError(f"{country}: expected one product_months part, found {paths}")
    months = pd.read_parquet(paths[0], columns=["input_hash", "month", "price", "n_rows", "currency"])
    months = months[months["input_hash"].isin(set(hashes))].reset_index(drop=True)
    if months.duplicated(["input_hash", "month"]).any():
        raise RuntimeError(f"{paths[0]}: repeats an (input_hash, month) key")
    missing = set(hashes) - set(months["input_hash"])
    if missing:
        raise RuntimeError(f"{country}: {len(missing)} products have no product_months row")
    return months


def month_fx(pm: pd.DataFrame, local: str) -> pd.DataFrame:
    """Each product-month at its month's rate, repriced into `local`.

    The month's rate is the mean of its daily USD->local rates, forward-filled
    by `build_fx_table`; the month is `fx_suspect` when any of those days' rate
    is implausible. A month quoted in another currency is repriced via USD
    (livingcost quotes New Zealand in USD: banded as NZD it sat at ~0.6x every
    other shop, blended in, and was trusted). One with no rate is left as
    quoted and marked `fx_suspect`.
    """
    pm = pm.assign(currency=pm["currency"].map(fx.normalize_currency_safe))
    known = pm["month"].dropna()
    start = pd.to_datetime(known.min(), format="%Y-%m")
    end = pd.to_datetime(known.max(), format="%Y-%m") + pd.offsets.MonthEnd(0)
    currencies = sorted(set(pm["currency"].dropna()) | {local})
    days = pd.DataFrame(
        [(c, d) for c in currencies for d in (start, end)], columns=["currency", "observation_date"]
    )
    table = fx._mark_suspect_rates(fx.build_fx_table(days), fx.PRICES_FX_CACHE)
    table["fx_rate"] = pd.to_numeric(table["fx_rate"], errors="coerce")
    table["month"] = month_of(pd.to_datetime(table["observation_date"]))
    rates = table.groupby(["currency", "month"]).agg(
        fx_rate=("fx_rate", "mean"), fx_suspect=("fx_suspect", "any")
    )

    def at(currency: pd.Series) -> tuple[pd.Series, pd.Series]:
        key = pd.MultiIndex.from_arrays([currency, pm["month"]])
        rate = pd.Series(rates["fx_rate"].reindex(key).to_numpy(), index=pm.index, dtype=float)
        bad = pd.Series(rates["fx_suspect"].reindex(key).to_numpy(), index=pm.index)
        usd = currency.eq("USD").to_numpy()
        rate[usd] = 1.0
        bad[usd] = False
        return rate, bad.fillna(False).astype(bool)

    own_rate, _ = at(pm["currency"])
    local_rate, local_bad = at(pd.Series(local, index=pm.index))
    foreign = pm["currency"].ne(local)
    ok = foreign & own_rate.gt(0) & local_rate.notna()
    stuck = foreign & ~ok
    price = pd.to_numeric(pm["price"], errors="coerce")
    pm = pm.copy()
    pm["currency_quoted"] = pm["currency"]
    pm["price_local"] = price.where(~ok, price / own_rate * local_rate)
    pm.loc[ok, "currency"] = local
    pm["fx_rate"] = local_rate.where(~stuck, own_rate)
    pm["fx_suspect"] = local_bad | stuck
    return pm


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


def run(country: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(dated rows, product-months) for `country`, each with its verdict."""
    products = load_products(country)
    local = products["currency"].mode().iloc[0]

    # Step 1, product grain: extraction and the basis check.
    ex = extract_products(products, products[["input_hash", "coicop_code"]])
    prod = products[["input_hash", "source", "country", "coicop_code", "product_name_original"]].merge(
        ex, on="input_hash", how="left", validate="one_to_one"
    )
    allowed = trust.allowed_bases(country)
    missing = sorted(set(prod["coicop_code"]) - set(allowed))
    if missing:
        raise RuntimeError(f"leaves missing from the basis map: {missing}")
    basis = prod["pricing_basis"]
    prod["basis_ok"] = [b in allowed[c] for b, c in zip(basis, prod["coicop_code"])]
    prod["size_qty"] = [
        trust.size_of(*t)[1]
        for t in zip(basis, prod["amount_value"], prod["count"], prod["multiplier"])
    ]
    # A piece count in a leaf sold by weight or volume ("3本セット", "6pack")
    # has no size, only pieces: it is imputed a size per piece like a sizeless
    # product, times its pieces (user 2026-09-27).
    measured = [bool(allowed[c] & {"mass", "volume"}) for c in prod["coicop_code"]]
    counted = ~prod["basis_ok"] & basis.eq("count") & measured & prod["size_qty"].gt(0)
    prod["_pieces"] = prod["size_qty"].where(counted, 1.0)
    prod["sizeless"] = ~prod["basis_ok"] & (basis.isna() | basis.eq("item") | counted)
    # An allowed item is one piece, the same quantity as a count of one: both
    # price per piece, so they share the count cell ("Thơm 1 trái" and "Thơm"
    # are one pineapple each) instead of thinning two cells.
    prod.loc[prod["basis_ok"] & basis.eq("item"), "standard_unit"] = "unit"
    prod["basis_mismatch"] = ~prod["basis_ok"] & ~prod["sizeless"]
    prod["size_source"] = pd.Series(np.where(prod["basis_ok"], "extracted", None), dtype=object)

    # Step 2, product x month: FX at the month's rate, unit value.
    months = load_months(country, prod["input_hash"])
    rows = months.merge(prod, on="input_hash", how="left", validate="many_to_one")
    rows = month_fx(rows, local)
    rows["observation_date"] = pd.to_datetime(rows["month"], format="%Y-%m", errors="coerce")
    n = len(rows)
    rows["_row"] = np.arange(n)
    rows["qa_price_positive"] = rows["price_local"].gt(0)
    rows["unit_value_local"] = pd.to_numeric(pd.Series([
        compute_unit_value(p, b, a, c, m)
        for p, b, a, c, m in zip(
            rows["price_local"], rows["pricing_basis"], rows["amount_value"], rows["count"], rows["multiplier"]
        )
    ], index=rows.index, dtype=object), errors="coerce")

    # Per-piece products from a shop whose own per-kg price says they are not
    # pieces (bags, bulk packs) leave before the band and are never imputed.
    # Evidence is pooled over months; the verdict is per (leaf, source).
    pieces = piece_table(rows[rows["basis_ok"]])
    failed = set(pieces.index[pieces["outside"] & pieces["ref"].eq("same source")])
    rows["piece_fail"] = rows["pricing_basis"].eq("item") & pd.Series(
        [k in failed for k in zip(rows["coicop_code"], rows["source"])], index=rows.index
    )

    # The band: extracted product-months in an allowed basis define it, twice
    # over. One row per product per month, so a month cell's support is its
    # count of distinct products.
    # Official series help define the band but are judged by their own
    # history (below), and never lend sizes to imputation.
    official = rows["source"].isin(trust.official_sources())
    is_ex = (
        rows["basis_ok"] & rows["qa_price_positive"] & rows["unit_value_local"].gt(0)
        & ~rows["piece_fail"]
    )
    extracted = rows[is_ex].reset_index(drop=True)
    base2 = trust.band(extracted, pd.Series(True, index=extracted.index))

    # Step 3, product grain: imputation. Sizes are drawn from in-band measured
    # products of the same country, one vote per product, not per month.
    pool = extracted[
        base2 & extracted["pricing_basis"].isin(["mass", "volume", "count"])
        & ~extracted["source"].isin(trust.official_sources())
    ]
    pool = pool.drop_duplicates("input_hash")
    todo = rows[rows["sizeless"] & rows["qa_price_positive"] & ~official]
    # A shop that sells the leaf per kg at the same price is quoting per kg.
    perkg = trust.per_kg_rows(extracted, todo)
    cand = trust.impute_candidates(pool, todo[~todo["_row"].isin(perkg["_row"])])

    # Step 4, product x month: the final band judges every row.
    both = pd.concat([extracted, perkg, cand], ignore_index=True)
    mask = pd.Series(np.r_[base2.to_numpy(), np.zeros(len(perkg) + len(cand), bool)], index=both.index)
    scored = flag_uv_outliers(both, group_cols=tuple(trust.CELL), baseline_mask=mask, k=trust.K)
    ne, npk = len(extracted), len(perkg)
    chosen = pd.concat(
        [scored.iloc[ne : ne + npk], trust.choose_fit(scored.iloc[ne + npk :].reset_index(drop=True))],
        ignore_index=True,
    )
    if chosen["_row"].duplicated().any():
        raise RuntimeError("imputation kept two sizes for one product-month")

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
    pm = pd.concat([judged, rest], ignore_index=True).sort_values("_row", ignore_index=True)
    if len(pm) != n or pm["_row"].duplicated().any():
        raise RuntimeError(f"product-month count moved: {n} in, {len(pm)} out")
    own = pm["source"].isin(trust.official_sources()) & pm["basis_ok"] & pm["unit_value_local"].gt(0)
    # Against the same month's official quotes, not the product's whole
    # history: South Sudan RTDI runs 4 -> 12,725 SSP over 2007-2026, and a
    # whole-history median put every early and late year out.
    med = pm[own].groupby(["source", *trust.CELL, "month"], dropna=False)["unit_value_local"].transform("median")
    pm.loc[own, "qa_level"] = np.where(
        (pm.loc[own, "unit_value_local"] / med).between(*OFFICIAL_BOUNDS), "official", "out"
    )

    pm["unit_value_usd"] = pm["unit_value_local"] / pm["fx_rate"]
    lo = pd.to_numeric(pm["standard_unit"].map(lambda u: PLAUSIBLE_USD.get(u, (None, None))[0]))
    hi = pd.to_numeric(pm["standard_unit"].map(lambda u: PLAUSIBLE_USD.get(u, (None, None))[1]))
    uv = pm["unit_value_usd"]
    pm["qa_uv_plausible"] = lo.isna() | uv.isna() | uv.between(lo, hi)
    pm["qa_fx"] = pm["fx_rate"].notna() & ~pm["fx_suspect"]
    pm["qa_uv_category"] = pm["qa_uv_category"].fillna(True).astype(bool)
    pm["stage_b_status"] = _status(pm)
    pm = pm.drop(columns=["_row", "_cand", "_cand_share", "_pieces"], errors="ignore")

    # Step 5, dated rows: the final join before publish.
    return join_dated(dated_rows(country, pm["input_hash"]), pm), pm


def dated_rows(country: str, hashes: pd.Series) -> pd.DataFrame:
    """The country's raw observation rows for `hashes`, read from concatenate's
    shards with the same date and price parsing prepare applied."""
    wanted = hashes.unique().tolist()
    selector = partition.selector_from_flags(None, None, country)
    frames = []
    for shard in partition.select([selector], PER_SOURCE_DIR):
        table = pq.read_table(shard.path, columns=_DATED_COLS, filters=[("input_hash", "in", wanted)])
        if table.num_rows:
            frames.append(table.to_pandas())
    rows = pd.concat(frames, ignore_index=True)
    rows["observation_date"] = parse_dates(rows["date"])
    rows["month"] = month_of(rows["observation_date"])
    rows["price_quoted"] = pd.to_numeric(
        pd.Series([parse_price(v, c) for v, c in zip(rows["price"], rows["currency"])], dtype=object),
        errors="coerce",
    )
    return rows.drop(columns=["price", "currency", "date"])


_VERDICT_COLS = [
    "input_hash", "month", "price", "price_local", "currency", "currency_quoted",
    "fx_rate", "coicop_code", "pricing_basis", "amount_value", "standard_unit",
    "count", "multiplier", "size_qty", "size_source", "unit_value_local",
    "unit_value_usd", "uv_robust_z", "cell_sources", "qa_level", "stage_b_status",
]


def join_dated(rows: pd.DataFrame, pm: pd.DataFrame) -> pd.DataFrame:
    """Each dated row takes its product-month's verdict, scaled to its own
    price. A row outside RATIO_BOUNDS of the product-month median (or with no
    positive price) does not inherit `trusted`."""
    out = rows.merge(
        pm[_VERDICT_COLS].rename(columns={"price": "month_price"}),
        on=["input_hash", "month"], how="left", validate="many_to_one", indicator=True,
    )
    orphan = out["_merge"].ne("both")
    if orphan.any():
        raise RuntimeError(f"{orphan.sum()} dated rows have no product-month (shards changed since prepare?)")
    ratio = out["price_quoted"] / out["month_price"]
    out["price_ratio"] = ratio
    out["price_local"] = out["price_local"] * ratio
    out["unit_value_local"] = out["unit_value_local"] * ratio
    out["unit_value_usd"] = out["unit_value_usd"] * ratio
    status = out["stage_b_status"].copy()
    trusted = status.eq("trusted")
    official = out["source"].isin(trust.official_sources())
    lo = np.where(official, OFFICIAL_BOUNDS[0], RATIO_BOUNDS[0])
    hi = np.where(official, OFFICIAL_BOUNDS[1], RATIO_BOUNDS[1])
    status[trusted & ~((ratio >= lo) & (ratio <= hi))] = "review_price_ratio"
    status[trusted & ~out["price_quoted"].gt(0)] = "review_zero_price"
    out["stage_b_status"] = status
    out["trusted"] = status.eq("trusted")
    return out.drop(columns=["_merge"])


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
        # Imputed sizes are trusted at A-B only; imputed_fit is accepted like
        # imputed_mode (user, 2026-09-26) and stays tagged by `size_source`.
        src.isin(["imputed_mode", "imputed_fit", "per_kg"]) & level.eq("C"),
        ~df["qa_uv_plausible"],
        ~df["qa_fx"],
    ]
    choices = [
        "review_zero_price", "review_basis", "review_missing_qty",
        "review_piece", "review_uv_category", "review_uv_unscored", "review_uv_out",
        "review_level", "review_uv_implausible", "review_fx",
    ]
    return np.select(conditions, choices, default="trusted").astype(object)


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


def report(out: pd.DataFrame, pm: pd.DataFrame) -> str:
    """Counts on the dated rows, plus the agent triggers."""
    lines = [
        f"rows {len(out):,}  product-months {len(pm):,}  products {out['input_hash'].nunique():,}"
    ]
    t = out[out["trusted"]]
    lines.append(f"trusted {len(t):,}")
    lines.append("\ntrusted by qa_level x size_source")
    lines.append(pd.crosstab(t["qa_level"], t["size_source"], margins=True).to_string())
    lines.append("\nall rows by stage_b_status x size_source")
    lines.append(pd.crosstab(out["stage_b_status"], out["size_source"].fillna("none"), margins=True).to_string())
    lines.append("\nbasis disagreement: leaves whose extracted products mostly sit outside the map")
    prods = pm.drop_duplicates("input_hash")
    sized = prods[prods["pricing_basis"].notna() & prods["pricing_basis"].ne("item")]
    g = sized.groupby("coicop_code").agg(products=("basis_ok", "size"), in_map=("basis_ok", "mean"))
    lines.append(g[(g["products"] >= 30) & (g["in_map"] < 0.5)].sort_values("products", ascending=False).to_string())
    ab = out["qa_level"].isin(["A", "B"])
    share = ab.groupby(out["source"]).mean()
    lines.append(f"\nA+B share by source (country {ab.mean():.1%}; patch-agent trigger >= 10 points below)")
    lines.append(pd.DataFrame({"rows": out["source"].value_counts(), "ab_share": share}).sort_values("rows", ascending=False).to_string())
    outs = out["qa_level"].eq("out").groupby(out["coicop_code"]).agg(["size", "mean"])
    lines.append("\nleaves with out share > 5% (review-agent trigger)")
    lines.append(outs[(outs["mean"] > 0.05) & (outs["size"] >= 30)].sort_values("size", ascending=False).to_string())
    lines.append("\nimplied piece weight outside PIECE_BOUNDS x piece_kg (same source: excluded as review_piece; country: review only)")
    lines.append(piece_table(pm[pm["size_source"].eq("extracted")]).query("outside").to_string())
    return "\n".join(lines)


_SAMPLE_COLS = [
    "source", "product_name", "coicop_code", "price_local", "pricing_basis",
    "amount_value", "count", "multiplier", "standard_unit", "unit_value_local",
    "unit_value_usd", "size_source", "qa_level", "uv_robust_z", "stage_b_status",
]


def write(country: str, out: pd.DataFrame, pm: pd.DataFrame) -> None:
    root = OUT_ROOT / decisions_store.part_name(country)
    root.mkdir(parents=True, exist_ok=True)
    out.to_parquet(root / "observations.parquet", index=False)
    out[out["trusted"]].to_parquet(root / "trusted_observations.parquet", index=False)
    pm.to_parquet(root / "product_months.parquet", index=False)
    (root / "report.txt").write_text(report(out, pm))
    # Hand-check samples (spec evaluation step 2): 100 A/B rows, 50 imputed.
    ab = out[out["trusted"] & out["qa_level"].isin(["A", "B"])]
    ab.sample(min(100, len(ab)), random_state=0)[_SAMPLE_COLS].to_csv(root / "check_ab.csv", index=False)
    imp = out[out["size_source"].isin(["imputed_mode", "imputed_fit"])]
    imp.sample(min(50, len(imp)), random_state=0)[_SAMPLE_COLS].to_csv(root / "check_imputed.csv", index=False)


@click.command("stage-b")
@click.option("--country", required=True, help="Country slug, e.g. vietnam.")
def stage_b(country: str) -> None:
    """Stage B for one country: 01 + 02.1 extraction, basis map, band, trust."""
    out, pm = run(country)
    write(country, out, pm)
    click.echo(report(out, pm))
    click.echo(f"\nwrote {OUT_ROOT / decisions_store.part_name(country)}")
