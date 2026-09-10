"""Render the global retail-price dashboard from the build parquet.

Two views, one HTML file, vendored Chart.js inlined (WB intranet
blocks cdn.jsdelivr.net):
  - Current snapshot: COICOP-leaf country heat table of median USD/unit
    from the dedup'd snapshot.
  - Historical: per-COICOP-leaf line chart of monthly USD/unit medians,
    one line per country, gated to 2024-03-06+ (FX coverage floor).

Every leaf is shown on ONE unit. `_to_display_units` converts a leaf's other
units into its display unit before either view is built, so a leaf is one row
and one series rather than one per unit it happened to be sold in.

The unit-value grain is `coicop_code` (the deepest leaf the classifier
assigns); the retired cascade's `sub_label_id` sub-grain is no longer
produced, so each COICOP leaf is one row/series.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from prices.build import unit_collapse
from prices.build.sold_by_item import SOLD_BY_ITEM_LEAVES
from prices.coicop import RESIDUAL_TITLE_RE, residual_leaves
from prices.rtcal import fills as fills_mod

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_DIR = REPO_ROOT / "data" / "prices" / "build"
OBSERVATIONS_PARQUET = BUILD_DIR / "global_prices_observations.parquet"
VENDOR_CHART_JS = (
    REPO_ROOT / "src" / "text" / "plotting" / "vendor" / "chart.umd.min.js"
)
HTML_TEMPLATE_PATH = Path(__file__).resolve().parent / "_publish_template.html"
DASHBOARD_HTML = REPO_ROOT / "outputs" / "prices" / "global_prices_dashboard.html"
COICOP_XLSX = REPO_ROOT / "data" / "prices" / "enrich" / "coicop_categories.xlsx"
COUNTRIES_YAML = REPO_ROOT / "src" / "configs" / "countries.yaml"
REGIONS_YAML = REPO_ROOT / "src" / "configs" / "regions.yaml"

CURRENT_LOOKBACK_DAYS = 60
FX_HISTORY_FLOOR = pd.Timestamp("2013-01-01")
MIN_OBS_PER_CELL = 1
# Only rows whose trust_level is in this set reach the published dashboard.
# Cache rows without trust_level (legacy v1-era) are coalesced to "high" by
# the build stage, so this default is conservative without dropping vetted data.
PUBLISH_TRUST_LEVELS = frozenset({"high"})

# `item` and `unit` both carry the price of ONE countable piece; they differ
# only in how it was reached. `unit` divides a multipack price by an explicit
# count marker; `item` is the extraction ladder's catch-all, trusted only where
# SOLD_BY_ITEM_LEAVES says the commodity is genuinely an indivisible piece.
# Displaying them apart splits one quantity across two rows, so on those leaves
# they are folded into a single label. The fold is deliberately gated on the
# allowlist rather than applied to every `item` row: off-allowlist `item` means
# "no quantity found", which is not a piece price and must never merge.
PIECE_UNITS = frozenset({"item", "unit"})
MERGED_PIECE_UNIT = "each"

TYPICAL_MASS_CSV = BUILD_DIR / "leaf_typical_mass.csv"
SUPPRESSED_PARQUET = BUILD_DIR / "global_prices_suppressed_units.parquet"

# The residual-leaf rule now lives in `prices.coicop`, because the explorer has
# to apply exactly the same one. On this corpus it selects 52 leaves -- 20.7% of
# the table's rows and 31.9% of its observations -- so they cannot simply be
# deleted without the table looking gutted, and they cannot be left unmarked
# without inviting a comparison that does not mean anything.
_RESIDUAL_TITLE_RE = RESIDUAL_TITLE_RE
_residual_leaves = residual_leaves

_COICOP_RE = re.compile(r"^(\d+(?:\.\d+)*)")
_ND_SUFFIX_RE = re.compile(r"\s*\(ND\)\s*$")


def _normalize_coicop(code) -> str | None:
    if code is None or pd.isna(code):
        return None
    m = _COICOP_RE.match(str(code))
    return m.group(1) if m else None


def _load_coicop_titles() -> dict[str, str]:
    if not COICOP_XLSX.exists():
        return {}
    df = pd.read_excel(COICOP_XLSX)
    df = df[df["code"].notna()].copy()
    df["code"] = df["code"].astype(str)
    df["title"] = (
        df["title"].astype(str).str.replace(_ND_SUFFIX_RE, "", regex=True).str.strip()
    )
    return dict(zip(df["code"], df["title"]))


def _load_country_names() -> dict[str, str]:
    if not COUNTRIES_YAML.exists():
        return {}
    data = yaml.safe_load(COUNTRIES_YAML.read_text()) or {}
    return {slug: meta.get("name", slug) for slug, meta in data.items()}


def _load_regions() -> tuple[dict[str, str], list[dict[str, str]]]:
    """(country slug → region key, ordered region metadata).

    Region order follows regions.yaml so the columns stay stable across runs.
    """
    if not REGIONS_YAML.exists():
        return {}, []
    topo = yaml.safe_load(REGIONS_YAML.read_text()) or {}
    of_country: dict[str, str] = {}
    order: list[dict[str, str]] = []
    for key, meta in topo.items():
        order.append({"key": key, "label": meta.get("name", key)})
        for sub in (meta.get("subregions") or {}).values():
            for slug in sub.get("countries") or []:
                of_country[slug] = key
    return of_country, order


def _fold_piece_units(df: pd.DataFrame) -> pd.DataFrame:
    """Fold item/unit into one label on the leaves that vet `item` as genuine."""
    fold = df["coicop_code"].isin(SOLD_BY_ITEM_LEAVES) & df["standard_unit"].isin(
        PIECE_UNITS
    )
    if not fold.any():
        return df
    df = df.copy()
    df.loc[fold, "standard_unit"] = MERGED_PIECE_UNIT
    logger.info(
        "folded %d item/unit rows to %r across %d leaves",
        int(fold.sum()),
        MERGED_PIECE_UNIT,
        int(df.loc[fold, "coicop_code"].nunique()),
    )
    return df


def _to_display_units(df: pd.DataFrame) -> pd.DataFrame:
    """Put every row of a leaf on one unit, so the table has one row per leaf.

    Runs once, before both aggregations, so the current snapshot and the
    monthly series cannot disagree about which unit a leaf is quoted in. The
    piece fold runs first because `unit_collapse` votes on unit labels, and
    `item`/`unit` are two spellings of one piece price on the allowlisted
    leaves -- splitting that vote could hand a leaf to the loser.

    Rows that cannot be converted are written out rather than dropped in
    silence; that file is the answer to "why is this leaf missing here".
    """
    df = df.copy()
    df["coicop_code"] = df["coicop_code"].map(_normalize_coicop)
    df = df.dropna(subset=["coicop_code", "standard_unit"])
    df = _fold_piece_units(df)

    typical_mass = (
        pd.read_csv(TYPICAL_MASS_CSV) if TYPICAL_MASS_CSV.exists() else pd.DataFrame()
    )
    if typical_mass.empty:
        logger.warning("%s missing — piece rows cannot convert", TYPICAL_MASS_CSV)

    kept, dropped = unit_collapse.collapse(df, typical_mass)
    if not dropped.empty:
        SUPPRESSED_PARQUET.parent.mkdir(parents=True, exist_ok=True)
        dropped.to_parquet(SUPPRESSED_PARQUET, index=False)
        logger.info(
            "suppressed %d unconvertible rows over %d leaves -> %s",
            len(dropped),
            dropped["coicop_code"].nunique(),
            SUPPRESSED_PARQUET,
        )
    return kept


def _cell_key(code: str, unit: str) -> str:
    """Row identity for the heat table: a COICOP leaf measured in one unit."""
    return f"{code}|{unit}"


def _humanize_slug(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title()


def _current_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate observations within the last CURRENT_LOOKBACK_DAYS to a
    (coicop_code, country, standard_unit) median. Rows without a parseable
    observation_date are excluded.

    standard_unit stays in the grain even though `_to_display_units` has
    already made it constant within a leaf: keeping it means the groupby is
    what enforces that invariant rather than trusting it, and it carries the
    unit through to the chart axis.
    """
    df = df.copy()
    df["coicop_code"] = df["coicop_code"].map(_normalize_coicop)
    cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=CURRENT_LOOKBACK_DAYS)
    df = df[df["observation_date"] >= cutoff]
    df = _fold_piece_units(df)
    g = (
        df.dropna(subset=["unit_value_usd", "coicop_code", "standard_unit"])
        .groupby(["coicop_code", "country", "standard_unit"])
        .agg(
            median_usd=("unit_value_usd", "median"),
            n_all=("unit_value_usd", "size"),
            # Distinct shelf items behind the cell, which is what the table
            # reports as `n=`. NOT n_obs: one product priced weekly for a year
            # is 52 observations of the same thing, and reporting that as the
            # evidence base overstates it by the scrape cadence.
            n_products=("product_name", "nunique"),
            n_imputed=("imputed", "sum"),
            last_seen=("observation_date", "max"),
        )
        .reset_index()
    )
    return _split_imputed(g)


def _split_imputed(g: pd.DataFrame) -> pd.DataFrame:
    """Turn a pooled count into observed / imputed / share, and apply the gate.

    `n_obs` keeps its old meaning -- measured rows -- so every reader of it is
    unchanged. `imputed` is the cell with no measured price at all, which is the
    one a reader most needs marked; `imp_share` is the finer reading for cells
    that mix the two.
    """
    g["n_imputed"] = g["n_imputed"].fillna(0).astype(int)
    g["n_obs"] = (g["n_all"] - g["n_imputed"]).astype(int)
    g["imp_share"] = (g["n_imputed"] / g["n_all"]).where(g["n_all"] > 0, 0.0)
    g["imputed"] = g["n_obs"].eq(0)
    g = g.drop(columns="n_all")
    return g[(g["n_obs"] >= MIN_OBS_PER_CELL) | (g["n_imputed"] > 0)]


def _drop_pruned_rows(df: pd.DataFrame, pruned: pd.DataFrame) -> pd.DataFrame:
    """Remove observations sitting in a cell RT-CAL rejected as an obvious error.

    The dashboards have to agree about what is real. If the explorer refuses to
    draw a loaf of bread at US$108/kg and this one still charts it, the two are
    reporting different corpora, and the reader has no way to tell which. So the
    same rejection list drives both.
    """
    if pruned.empty or df.empty:
        return df
    key = df["observation_date"].dt.to_period("M").astype(str)
    tup = list(
        zip(
            df["country"].astype(str),
            df["coicop_code"].astype(str),
            df["standard_unit"].astype(str),
            key,
        )
    )
    bad = set(map(tuple, pruned[fills_mod.CELL_KEY].astype(str).values))
    return df[[t not in bad for t in tup]]


def _fill_rows(obs: pd.DataFrame, fills: pd.DataFrame) -> pd.DataFrame:
    """Append released fills to the observation frame as rows, flagged.

    They used to be appended to the MONTHLY series alone, and only where a
    series already existed on measured data. Both restrictions are gone: a fill
    is an observation-shaped row from here on, so it reaches the current
    snapshot and the heat table, the region and World medians, and the coverage
    cutoff -- every aggregate this file builds -- exactly as a measured price
    does. What keeps it honest is `imputed`, which travels with it to the
    payload, and `imp_share` on every aggregate it lands in.

    Three things have to be lined up first, and each was a way to get this
    wrong:

    REGION. `obs` has already been cut to the build's countries; the fills table
    has not. Appending it whole would put countries in a regional dashboard that
    the region filter had just taken out.

    DISPLAY UNIT. RT-CAL keys its cells on the unit the summary parquet carries,
    while `_to_display_units` has already put every observation of a leaf onto
    ONE unit, rescaling values on the way. A raw fill would either land on a
    second row for a leaf that is supposed to have one, or sit on a per-piece
    scale in a per-kilo row. So the fills go through the same conversion, under
    the display units the OBSERVATIONS chose -- a modelled row never votes on
    how a commodity is sold. A fill on a leaf with no defensible conversion is
    dropped, exactly as an observation would be.

    DATE. `period` is a "YYYY-MM" string in RT-CAL's tables and a Timestamp
    here, so the conversion happens once, at this boundary. A fill is dated to
    the START of its month, which is what puts it inside or outside the
    snapshot's rolling window -- a fill for last month counts as last month.
    """
    obs = obs.copy()
    obs["imputed"] = False
    if fills.empty:
        return obs

    f = fills[fills["country"].isin(set(obs["country"].unique()))].copy()
    if f.empty:
        return obs
    f["coicop_code"] = f["coicop_code"].map(_normalize_coicop)
    f = f.dropna(subset=["coicop_code", "standard_unit"])
    f["observation_date"] = pd.to_datetime(f["period"] + "-01")
    f = f.rename(columns={"usd": "unit_value_usd"})

    display = (
        obs.groupby("coicop_code")["standard_unit"].agg(lambda s: s.iloc[0]).to_dict()
    )
    typical_mass = (
        pd.read_csv(TYPICAL_MASS_CSV) if TYPICAL_MASS_CSV.exists() else pd.DataFrame()
    )
    before = len(f)
    f, _ = unit_collapse.collapse(
        f, typical_mass, value_cols=("unit_value_usd",), canonical=display
    )
    f["imputed"] = True
    f["product_name"] = None
    keep = [
        "country",
        "coicop_code",
        "standard_unit",
        "observation_date",
        "unit_value_usd",
        "product_name",
        "imputed",
        "prob",
    ]
    out = pd.concat([obs, f[keep]], ignore_index=True)
    logger.info(
        "appended %d of %d released fills to %d observation rows",
        len(f),
        before,
        len(obs),
    )
    return out


def _monthly_series(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["observation_date"] >= FX_HISTORY_FLOOR].copy()
    sub = sub.dropna(subset=["unit_value_usd", "coicop_code"])
    sub["coicop_code"] = sub["coicop_code"].map(_normalize_coicop)
    sub = sub[sub["coicop_code"].notna()]
    sub = sub.dropna(subset=["standard_unit"])
    sub = _fold_piece_units(sub)
    sub["month"] = sub["observation_date"].dt.to_period("M").dt.to_timestamp()
    g = (
        sub.groupby(["coicop_code", "country", "month", "standard_unit"])
        .agg(
            median_usd=("unit_value_usd", "median"),
            n_all=("unit_value_usd", "size"),
            n_imputed=("imputed", "sum"),
        )
        .reset_index()
    )
    return _split_imputed(g)


def _region_stats(
    keyed: pd.DataFrame, region_cols: list[dict[str, str]]
) -> tuple[
    dict[str, dict[str, float]],
    dict[str, dict[str, int]],
    dict[str, dict[str, int]],
    dict[str, dict[str, float]],
]:
    """Region medians plus two different counts of what stands behind them.

    The median is unweighted over country medians, so the number of countries
    is what describes the statistic. The number of distinct products is what
    describes the evidence, and it is the one the table shows. Both are
    returned because showing one while the tooltip explains the other would
    make the tooltip false.

    Products are summed across countries without a cross-country dedup: the
    same name on a Thai and a Vietnamese shelf is two priced items, not one.
    """
    medians: dict[str, dict[str, float]] = {}
    counts: dict[str, dict[str, int]] = {}
    products: dict[str, dict[str, int]] = {}
    shares: dict[str, dict[str, float]] = {}
    for (code, unit), grp in keyed.groupby(["coicop_code", "standard_unit"]):
        med: dict[str, float] = {}
        cnt: dict[str, int] = {}
        prod: dict[str, int] = {}
        imp: dict[str, float] = {}
        for col in region_cols:
            sub = (
                grp
                if col["key"] == "world"
                else grp.loc[grp["_region"].eq(col["key"])]
            )
            s = sub["median_usd"]
            have = s.notna()
            n = int(have.sum())
            if n:
                med[col["key"]] = float(s.median())
                cnt[col["key"]] = n
                prod[col["key"]] = int(sub.loc[have, "n_products"].sum())
                # The median is over COUNTRY medians, so its provenance is the
                # mean imputed share of the countries in it -- not of the rows.
                imp[col["key"]] = round(
                    float(sub.loc[have, "imp_share"].mean()), 4
                )
        key = _cell_key(code, unit)
        medians[key] = med
        counts[key] = cnt
        products[key] = prod
        shares[key] = imp
    return medians, counts, products, shares


def _coverage_cutoff(
    current: pd.DataFrame, residual: frozenset[str]
) -> tuple[int, set[str], dict]:
    """Countries in the bottom quartile by breadth of COICOP coverage.

    Breadth is counted over named leaves only. A residual leaf is a catch-all,
    so crediting a country for reaching one would reward the classifier giving
    up rather than the country having a real price for a real category.

    The cut is the 25th percentile of the count, applied strictly (``<``).
    Counts are small integers and pile up on ties, so ``<=`` would carry every
    country sitting exactly on the boundary over the line with it and drop
    materially more than the quartile asked for.
    """
    named = current[~current["coicop_code"].isin(residual)]
    per_country = named.groupby("country")["coicop_code"].nunique()
    if per_country.empty:
        return 0, set(), {"median": 0, "n_countries": 0, "n_named_leaves": 0}
    threshold = int(np.percentile(per_country.to_numpy(), 25))
    low = set(per_country.index[per_country < threshold])
    stats = {
        "median": int(per_country.median()),
        "n_countries": int(per_country.size),
        "n_named_leaves": int(named["coicop_code"].nunique()),
        "n_dropped": len(low),
    }
    return threshold, low, stats


# The imputation fields on a record that has none. The global dashboard's
# monthly array runs to millions of rows and the file is already ~90 MB, so
# three constant fields per row is tens of megabytes of "nothing was modelled
# here" -- which is what an absent key says for free. A client reading these
# must treat missing as false / zero, which is what `undefined` does in JS
# anyway.
_IMP_FIELDS = ("imputed", "imp_share", "n_imputed")


def _lean(r: dict) -> dict:
    if r.get("n_imputed"):
        return r
    return {k: v for k, v in r.items() if k not in _IMP_FIELDS}


def _payload(
    current: pd.DataFrame, monthly: pd.DataFrame, region: str | None = None
) -> dict:
    coicop_titles = _load_coicop_titles()
    country_names = _load_country_names()
    residual = _residual_leaves(coicop_titles)

    used_countries = sorted(
        set(current["country"].unique())
        | (set(monthly["country"].unique()) if not monthly.empty else set())
    )
    country_display = {
        c: country_names.get(c, _humanize_slug(c)) for c in used_countries
    }

    # Hierarchy titles for all ancestor levels of the leaves we actually display
    coicop_used: dict[str, str] = {}
    for code in current["coicop_code"].dropna().unique():
        parts = str(code).split(".")
        for i in range(1, len(parts) + 1):
            anc = ".".join(parts[:i])
            if anc in coicop_titles:
                coicop_used[anc] = coicop_titles[anc]

    # Median of country-level medians per coicop leaf, one entry per region
    # plus "world" (each country one observation, unweighted). The unit is
    # still in the key, but it is constant within a leaf by the time this
    # runs, so this is one entry per leaf.
    of_country, region_order = _load_regions()
    # A build restricted to one region has already dropped every other
    # country's rows (see `publish`), so a "World" column here would just be
    # the region's own median wearing a bigger label -- a genuine lie, not a
    # rounding quirk. Ship only that region's column instead of computing a
    # World figure that no longer means "world".
    if region is not None:
        region_cols = [rc for rc in region_order if rc["key"] == region]
    else:
        region_cols = [{"key": "world", "label": "World"}] + region_order
    # Residual leaves get no region or world figure. A cross-country median over
    # "Other bakery products" compares one country's croissants against another's
    # flatbread, and the number carries the same authority on the page as a real
    # one. Their per-country cells stay, so the coverage is still legible; it is
    # the comparison across countries that is withheld, and the row is marked so
    # the gap reads as deliberate rather than missing.
    keyed = current.assign(_region=current["country"].map(of_country))
    keyed = keyed[~keyed["coicop_code"].isin(residual)]
    region_medians, region_n_countries, region_n_products, region_imp = _region_stats(
        keyed, region_cols
    )

    # The low-coverage toggle drops countries from the table, so it has to drop
    # them from the region and world medians too: a comparison figure that still
    # averages in a country whose column the reader just hid is wrong in the one
    # direction nobody would check.
    threshold, low_coverage, coverage_stats = _coverage_cutoff(current, residual)
    kept = keyed[~keyed["country"].isin(low_coverage)]
    (
        region_medians_kept,
        region_n_countries_kept,
        region_n_products_kept,
        region_imp_kept,
    ) = _region_stats(kept, region_cols)

    shown = current[~current["coicop_code"].isin(residual)]
    shown_kept = shown[~shown["country"].isin(low_coverage)]

    def _kpi(cur: pd.DataFrame, shown: pd.DataFrame, n_countries: int) -> dict:
        """Headline counts, each over exactly the population it names.

        `products` used to be the row count of `current`, which is neither
        products nor the number the table totals -- one product priced weekly
        for two months is eight observations and one product. So `products` is
        now distinct shelf items and `observations` is the price readings behind
        them, and they are separate tiles because they are separate populations
        and a reader who sees only one of them cannot tell which they were shown.

        Everything here is scoped to the grid: this is the last
        CURRENT_LOOKBACK_DAYS of the countries in this build, which is what the
        heat table draws. Nothing counts the whole corpus.
        """
        return {
            "countries": n_countries,
            "coicop_leaves": int(shown["coicop_code"].nunique()),
            "products": int(cur["n_products"].sum()),
            "observations": int(cur["n_obs"].sum()),
            "cells": int(len(cur)),
            "imputed_cells": int(cur["imputed"].sum()),
        }

    kpi = _kpi(current, shown, len(country_display))
    kept_cur = current[~current["country"].isin(low_coverage)]
    kpi_kept = _kpi(
        kept_cur, shown_kept, len(country_display) - len(low_coverage)
    )

    cutoff = (
        (pd.Timestamp.now().normalize() - pd.Timedelta(days=CURRENT_LOOKBACK_DAYS))
        .date()
        .isoformat()
    )
    data_through = (
        pd.to_datetime(current["last_seen"], errors="coerce").max().date().isoformat()
        if not current.empty and current["last_seen"].notna().any()
        else None
    )
    return {
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "lookback_days": CURRENT_LOOKBACK_DAYS,
        "cutoff_date": cutoff,
        "data_through": data_through,
        "min_obs_per_cell": MIN_OBS_PER_CELL,
        "fx_floor": FX_HISTORY_FLOOR.date().isoformat(),
        "country_names": country_display,
        "coicop_titles": coicop_used,
        "region_cols": region_cols,
        "region_medians": region_medians,
        "region_n_countries": region_n_countries,
        "region_n_products": region_n_products,
        "region_medians_kept": region_medians_kept,
        "region_n_countries_kept": region_n_countries_kept,
        "region_n_products_kept": region_n_products_kept,
        # Share of each region/World median that came from a fill, as a mean
        # over the country medians it is a median of.
        "region_imp": region_imp,
        "region_imp_kept": region_imp_kept,
        "residual_leaves": sorted(residual & set(current["coicop_code"].dropna())),
        "low_coverage": sorted(low_coverage),
        "coverage_cutoff": {"categories": threshold, **coverage_stats},
        "kpi": kpi,
        "kpi_kept": kpi_kept,
        # What each KPI counts, in the payload rather than in the template, so
        # the tile and its explanation cannot drift apart.
        "kpi_notes": {
            "products": "distinct shelf items priced in the window",
            "observations": "price readings behind them; one item priced "
            "weekly is many observations of one product",
            "countries": "countries with at least one published cell",
            "coicop_leaves": "named COICOP leaves with a published cell",
            "cells": "(category, country, unit) cells in the table",
            "imputed_cells": "of those, cells with no measured price at all",
        },
        "imputed": {
            "cells": int(current["imputed"].sum()),
            "method": "rtcal_v1",
            "flag_field": "imputed",
            "share_field": "imp_share",
        },
        "current": [_lean(r) for r in current.to_dict(orient="records")],
        "monthly": [
            _lean({**r, "month": r["month"].date().isoformat()})
            for r in monthly.to_dict(orient="records")
        ],
    }


def _render(payload: dict, chart_js: str) -> str:
    data_json = json.dumps(payload, default=str)
    template = HTML_TEMPLATE_PATH.read_text()
    return template.replace("/*__CHART_JS__*/", chart_js).replace(
        "/*__DATA__*/", data_json
    )


def publish(region: str | None = None, out_path: Path | None = None) -> Path:
    """Render the dashboard, optionally restricted to one region's countries.

    The restriction happens here, before `_to_display_units` and both
    aggregations run, so a region build is a genuinely separate computation
    over a smaller country set -- not the global numbers with columns hidden
    in the browser. Every downstream figure (KPIs, region/World medians, the
    low-coverage cutoff, the monthly series) is consistent with what is on
    screen.
    """
    if not OBSERVATIONS_PARQUET.exists():
        raise FileNotFoundError(
            f"{OBSERVATIONS_PARQUET} not found — run `po prices build` first."
        )
    obs = pd.read_parquet(OBSERVATIONS_PARQUET)
    obs["observation_date"] = pd.to_datetime(obs["observation_date"], errors="coerce")
    obs = obs[obs["observation_date"].notna()]
    if "qa_status" in obs.columns:
        # qa_status == "trusted" already ANDs Layer-1 basis-ok, real quantity,
        # Layer-2 uv-inlier, and FX; it is the single publish gate when present.
        before = len(obs)
        obs = obs[obs["qa_status"] == "trusted"]
        logger.info("qa_status=='trusted' filter kept %d of %d rows", len(obs), before)
    elif "trust_level" in obs.columns:
        # Fallback for parquets predating the QA layer.
        before = len(obs)
        obs = obs[obs["trust_level"].fillna("high").isin(PUBLISH_TRUST_LEVELS)]
        logger.info(
            "trust_level filter (%s) kept %d of %d rows",
            sorted(PUBLISH_TRUST_LEVELS),
            len(obs),
            before,
        )
    if region is not None:
        of_country, region_order = _load_regions()
        if region not in {rc["key"] for rc in region_order}:
            raise ValueError(f"unknown region {region!r} (see regions.yaml)")
        before = len(obs)
        obs = obs[obs["country"].map(of_country) == region]
        logger.info("region==%r filter kept %d of %d rows", region, len(obs), before)
    obs = _to_display_units(obs)
    # Both empty unless `prices rtcal run` has been executed.
    #
    # Folded on the way in, because RT-CAL keys cells on the unit the summary
    # parquet carries while `_to_display_units` has already folded `item`/`unit`
    # to one label here. Comparing the two raw would miss 2.7% of fills and 2.4%
    # of pruned cells -- and both misses are silent, since one is an inner join
    # returning fewer rows and the other a tuple that simply fails to match.
    pruned = _fold_piece_units(fills_mod.load_pruned_cells())
    before = len(obs)
    obs = _drop_pruned_rows(obs, pruned)
    if len(obs) != before:
        logger.info(
            "rtcal pruning dropped %d of %d rows (%d rejected cells)",
            before - len(obs),
            before,
            len(pruned),
        )
    obs = _fill_rows(obs, _fold_piece_units(fills_mod.load_released_fills()))
    current = _current_snapshot(obs)
    monthly = _monthly_series(obs)

    payload = _payload(current, monthly, region=region)
    chart_js = VENDOR_CHART_JS.read_text()
    html = _render(payload, chart_js)

    out = out_path or DASHBOARD_HTML
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    logger.info(
        "wrote %s (%d current cells, %d monthly cells)",
        out,
        len(current),
        len(monthly),
    )
    return out


def run() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    publish()
