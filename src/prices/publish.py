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
from prices.explorer.profile import UNFILTERED, gate, stamp_unfiltered
from prices.explorer.sources import CELL_WINDOW_DAYS
from prices.rtcal import fills as fills_mod

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_DIR = REPO_ROOT / "data" / "prices" / "build"
OBSERVATIONS_PARQUET = BUILD_DIR / "global_prices_observations.parquet"
# The same rows pre-filtered to qa_status == "trusted", written by the build
# stage in the same run as the full frame. Verified equal to filtering the full
# frame in memory: 25,873,307 rows either way on the 2026-09-15 build, with
# identical per-country counts. Read in preference to the full frame because it
# is the artefact that DEFINES the published set; the qa_status filter below
# then runs over it as a free assertion, logging "kept N of N" when the file is
# what it claims to be.
TRUSTED_PARQUET = BUILD_DIR / "global_prices_trusted_observations.parquet"
# Upstream of the build entirely: what the classifier proposed, and what it
# accepted. The production model is hierlex_select_v1_20260910; the store is
# keyed on (name, country) -- one row per distinct product name per country,
# with no dates and no row counts -- so it only becomes an observation count by
# joining through `products_input`, which carries the date and the input_hash
# grain the classifier ran on.
ENRICH_DIR = REPO_ROOT / "data" / "prices" / "enrich"
HIERLEX_PRED_DIR = (
    ENRICH_DIR / "_hierlex_pred" / "hierlex_select_v1_20260910"
)
PRODUCTS_INPUT = ENRICH_DIR / "products_input.parquet"
# One row per input_hash carrying the state the classifier finished in and the
# code it settled on -- the artefact the build obeys, unlike the prediction
# store's base-threshold `accepted` flag.
DECISIONS_DIR = ENRICH_DIR / "cache" / "decisions_hierlex"
# States in which the classifier resolved a row to a code. `narrow_source` is
# a source-declared single leaf that short-circuits the model: still a
# decision, just not the model's.
DECIDED_STATES = frozenset({"classified", "narrow_source"})
VENDOR_CHART_JS = (
    REPO_ROOT / "src" / "text" / "plotting" / "vendor" / "chart.umd.min.js"
)
HTML_TEMPLATE_PATH = Path(__file__).resolve().parent / "_publish_template.html"
DASHBOARD_HTML = REPO_ROOT / "outputs" / "prices" / "global_prices_dashboard.html"
COICOP_XLSX = REPO_ROOT / "data" / "prices" / "enrich" / "coicop_categories.xlsx"
COUNTRIES_YAML = REPO_ROOT / "src" / "configs" / "countries.yaml"
REGIONS_YAML = REPO_ROOT / "src" / "configs" / "regions.yaml"

# The rolling window the "current" snapshot is taken over. Was the latest
# CALENDAR MONTH, which parked each cell on whatever month it was last scraped
# in and left thousands of cells resting on a single observation a few days
# into a new month; then a fixed 60, then 90 days, each set independently of
# the explorer dashboard's own window and free to drift from it. Both
# dashboards now share ONE number -- `CELL_WINDOW_DAYS`, decided at 90 days --
# so "current" means the same stretch of time on both pages and the two can no
# longer disagree about what "current" is.
CURRENT_LOOKBACK_DAYS = CELL_WINDOW_DAYS
# The two cell grids the page carries. "cur" is the rolling window the price
# dashboard also uses; "all" is every observation in the corpus. Both are built
# and both ship, because the question "are we losing observations" is answered
# by comparing them -- a loss visible only in the full history is structural,
# one visible only in the window is recent.
GRIDS = {"cur": CURRENT_LOOKBACK_DAYS, "all": None}
# Human labels for the qa_status values, used in the per-cell loss tooltip.
# Anything unmapped falls back to the raw value rather than being hidden.
QA_REASONS = {
    "review_missing_qty": "no resolvable quantity",
    "review_uv_outlier": "unit value an outlier",
    "review_uv_implausible": "unit value implausible",
    "review_uv_thin": "unit-value cell too thin",
    "review_uv_category": "unit value out of category range",
    "review_zero_price": "price was zero",
    "review_fx": "no FX rate",
}
FX_HISTORY_FLOOR = pd.Timestamp("2013-01-01")
# Already at its arithmetic floor: one observed price, or any fill.
MIN_OBS_PER_CELL = gate(1, 1)
# Named COICOP leaves a country must price in the window before its column is
# OFFERED to the low-coverage toggle. This replaces a 25th-percentile cut, and
# the replacement is the point rather than the number. A relative cutoff removes
# a quarter of the countries no matter how good the data gets, and it was doing
# exactly that: on the September 2026 corpus it labelled 50 of 202 countries
# "low coverage", among them Belgium (45 named leaves), Kuwait (45), Norway
# (31), Iceland (36) and Tanzania (43) -- and Northern Mariana Islands at 48,
# one leaf under a threshold that only existed because three quarters of the
# world happened to be above it. In EAP it labelled 10 of 38. A fixed floor of
# 10 named leaves out of 258 labels 8 globally and 1 in EAP, and it retires
# itself as the corpus fills, which the quartile never could.
COVERAGE_MIN_NAMED_LEAVES = gate(10, 0)
# Only rows whose trust_level is in this set reach the published dashboard.
# Cache rows without trust_level (legacy v1-era) are coalesced to "high" by
# the build stage, so this default is conservative without dropping vetted data.
PUBLISH_TRUST_LEVELS = frozenset({"high"})
# The only columns anything downstream of `publish` reads. The observations
# parquet carries 39, and reading all of them materialised 31M rows of
# `product_url`, `source`, `currency` and twenty-odd unused flags -- around
# 20 GB of object-dtype strings for columns no figure on the page depends on,
# which is what put the unrestricted build over this machine's 26 GB and got it
# SIGKILLed while a region build of the same code finished in seconds.
#
# Missing names are skipped rather than raising, so an older parquet still
# loads; `qa_status` and `trust_level` are the two publish gates and only one
# of them exists on any given vintage.
PUBLISH_COLUMNS = (
    "product_name",  # distinct shelf items behind a cell
    "country",
    "observation_date",
    "standard_unit",
    "coicop_code",
    "unit_value_local",  # unit_collapse rescales both value columns
    "unit_value_usd",
    "qa_status",  # the publish gate
    "trust_level",  # the pre-QA-layer fallback gate
)


def _read_publish_columns(path: Path) -> pd.DataFrame:
    """The observations frame narrowed to what this module actually uses.

    Replaces `build.aggregate.read_observations`, which drops the lineage
    columns and keeps everything else. The narrowing is not an optimisation
    detail: without it the global build does not run here at all.
    """
    import pyarrow.parquet as pq

    available = set(pq.ParquetFile(path).schema_arrow.names)
    missing = [c for c in PUBLISH_COLUMNS if c not in available]
    if missing:
        logger.info("parquet has no %s — skipping", ", ".join(missing))
    return pd.read_parquet(path, columns=[c for c in PUBLISH_COLUMNS if c in available])

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


def _pair_hash(df: pd.DataFrame, a: str, b: str) -> "np.ndarray":
    """Stable 64-bit hash of a (name, country) pair.

    The join is on a hash rather than the strings because the classifier store
    holds 35.7M pairs of free-text product names and the scan it joins against
    is 47.5M rows; holding both as objects is several GB on a box that is
    already carrying a 16 GB frame later in the same run. Column NAMES do not
    enter pandas' row hash -- only values and order -- so the two stores hash
    identically under different column names.
    """
    return pd.util.hash_pandas_object(
        df[[a, b]].rename(columns={a: "k0", b: "k1"}), index=False
    ).to_numpy()


def _classify_funnel(countries: set[str] | None = None) -> pd.DataFrame | None:
    """Rows per (leaf, country) at the classify and decide stages.

    Reads the DECISIONS store, which is the artefact the build actually obeys:
    one row per input_hash, carrying the state the classifier finished in and
    the code it settled on. The prediction store is the wrong source for this
    -- its `accepted` flag is a base threshold that target_95 re-thresholded
    downstream, and taking it at face value puts EAP's decided count below its
    trusted count, which an upstream stage cannot be.

    C counts every row the classifier SCORED. D counts the rows it resolved to
    a code: `classified` plus `narrow_source`. `narrow_source` is a row whose
    source declared a single COICOP leaf, which short-circuits the model
    (classify.py) -- it is still a decision, just not the model's, so it
    belongs in D. `rejected` rows are scored but unresolved and appear in C
    only; they are attributed by `leaf_top1`, the model's best candidate,
    because `coicop_code` is null for exactly that state and no other.

    WEIGHTED BY `n_rows`. products_input is deduplicated on input_hash and
    each row stands for that many raw rows, which the build expands again.
    Counting deduplicated rows instead gives EAP 2.59M classified against
    12.16M observations -- fewer inputs than outputs, which is impossible.

    ALL-TIME ONLY. products_input carries one collapsed date per deduplicated
    row and the build re-dates the same rows: EAP holds 4.21M rows dated 2026
    there against 7.87M in the observations parquet, with all-time totals
    matching to 0.4%. The rows correspond; the dates do not. A windowed figure
    here would be precise and wrong.
    """
    import numpy as np

    if not DECISIONS_DIR.is_dir() or not PRODUCTS_INPUT.exists():
        logger.warning(
            "no decisions store at %s -- cells ship without a classified count",
            DECISIONS_DIR,
        )
        return None

    parts = sorted(DECISIONS_DIR.glob("*.parquet"))
    if countries is not None:
        parts = [p for p in parts if p.stem in countries]
    if not parts:
        return None

    hs, leaves, ctys, dec = [], [], [], []
    states: dict[str, int] = {}
    for p in parts:
        d = pd.read_parquet(
            p, columns=["input_hash", "country", "coicop_code", "state", "leaf_top1"]
        )
        for s, n in d["state"].value_counts().items():
            states[s] = states.get(s, 0) + int(n)
        # `unembedded` was never scored, so it is not a classifier count at all.
        d = d[d["state"].ne("unembedded")]
        if d.empty:
            continue
        hs.append(pd.util.hash_pandas_object(d["input_hash"], index=False).to_numpy())
        leaves.append(d["coicop_code"].fillna(d["leaf_top1"]).to_numpy())
        ctys.append(d["country"].to_numpy())
        dec.append(d["state"].isin(DECIDED_STATES).to_numpy())
    if not hs:
        return None
    h = np.concatenate(hs)
    order = np.argsort(h, kind="stable")
    h = h[order]
    leaf_codes, leaf_uniq = pd.factorize(pd.Index(np.concatenate(leaves))[order])
    cty_codes, cty_uniq = pd.factorize(pd.Index(np.concatenate(ctys))[order])
    dec = np.concatenate(dec)[order]
    logger.info(
        "decisions store: %d country parts, %d scored rows (%d resolved to a "
        "code); states %s",
        len(parts), len(h), int(dec.sum()),
        ", ".join(f"{k}={v}" for k, v in sorted(states.items())),
    )

    import pyarrow.dataset as ds

    rows: dict[tuple, list] = {}
    scanned = matched = 0
    for b in ds.dataset(PRODUCTS_INPUT, format="parquet").to_batches(
        columns=["input_hash", "n_rows"]
    ):
        df = b.to_pandas()
        scanned += len(df)
        hh = pd.util.hash_pandas_object(df["input_hash"], index=False).to_numpy()
        pos = np.clip(np.searchsorted(h, hh), 0, len(h) - 1)
        hit = h[pos] == hh
        if not hit.any():
            continue
        matched += int(hit.sum())
        w = pd.to_numeric(df["n_rows"], errors="coerce").fillna(1).to_numpy()[hit]
        sub = pd.DataFrame({
            "coicop_code": leaf_uniq.take(leaf_codes[pos[hit]]),
            "country": cty_uniq.take(cty_codes[pos[hit]]),
            "w": w,
            "wdec": np.where(dec[pos[hit]], w, 0),
        })
        g = sub.groupby(["coicop_code", "country"]).agg(
            n_classified=("w", "sum"), n_decided=("wdec", "sum")
        )
        for k, v in g.iterrows():
            cell = rows.setdefault(k, [0, 0])
            cell[0] += int(v.n_classified)
            cell[1] += int(v.n_decided)
    out = pd.DataFrame(
        [(k[0], k[1], v[0], v[1]) for k, v in rows.items()],
        columns=["coicop_code", "country", "n_classified", "n_decided"],
    )
    out["coicop_code"] = out["coicop_code"].map(_normalize_coicop)
    out = out.dropna(subset=["coicop_code"])
    out = out.groupby(["coicop_code", "country"], as_index=False).sum()
    logger.info(
        "classify funnel: %d of %d products_input rows carry a decision; "
        "%d raw rows classified -> %d decided over %d cells",
        matched, scanned,
        int(out["n_classified"].sum()), int(out["n_decided"].sum()), len(out),
    )
    return out


def _window_cutoff(days: int | None) -> pd.Timestamp:
    """Start of a grid's window. `None` means the whole corpus."""
    if days is None:
        return pd.Timestamp.min
    return pd.Timestamp.now().normalize() - pd.Timedelta(days=days)


def _top_reason(byreason: pd.Series) -> pd.DataFrame:
    """The single largest qa_status per (leaf, country), and its count.

    A cell loses rows for several reasons at once and naming all of them turns
    a tooltip into a table. The largest one answers "how is THIS cell losing
    observations" in a phrase, and the stage totals beside it stop that phrase
    from reading as the whole loss.
    """
    if byreason.empty:
        return pd.DataFrame(
            columns=["coicop_code", "country", "top_qa", "n_top_qa"]
        )
    s = byreason.sort_values(ascending=False)
    top = s.groupby(level=[0, 1], sort=False).head(1).reset_index()
    top.columns = ["coicop_code", "country", "top_qa", "n_top_qa"]
    return top


def _stage_counts(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Rows per (leaf, country) at one point in the pipeline, per grid window.

    Differencing two of these is how the page knows where observations went:
    the funnel is not recorded anywhere, so it is measured by counting the
    frame before and after each stage rather than by trusting a log line.
    """
    out: dict[str, pd.Series] = {}
    for key, days in GRIDS.items():
        w = df[df["observation_date"] >= _window_cutoff(days)]
        out[key] = w.groupby(["coicop_code", "country"]).size()
    return out


def _loss_funnel(
    path: Path, countries: set[str] | None = None
) -> dict[str, pd.DataFrame]:
    """What was collected per (leaf, country), and what QA did to it.

    THE DENOMINATOR THE PAGE HAS NEVER SHOWN. A cell reading 14 has always
    meant "14 rows survived", with no way to tell 14-of-14 from 14-of-900 --
    opposite findings about a source. This counts the full frame before any
    gate, and attributes the QA share of the loss to a reason.

    Grouped on (coicop_code, country) and NOT on standard_unit. Every leaf is
    put onto one display unit downstream, so the unit adds nothing to cell
    identity -- and a row that failed `review_missing_qty` has no resolvable
    quantity, so conditioning the denominator on unit agreement would drop the
    largest failure class from the very count that exists to show it.

    Reads the widest frame this module touches (product_name over 31M rows) and
    returns only per-cell aggregates, so the caller can free it before the
    trusted frame is loaded. Both are ~8-16 GB; neither machine nor patience
    survives holding them at once.
    """
    df = pd.read_parquet(
        path,
        columns=["coicop_code", "country", "observation_date", "qa_status",
                 "product_name"],
    )
    df["observation_date"] = pd.to_datetime(df["observation_date"], errors="coerce")
    df = df[df["observation_date"].notna()]
    # SCOPE THE DENOMINATOR TO THE BUILD. The trusted frame is cut to the
    # region a few lines later in `publish`; if the funnel is not cut with it,
    # every country outside the region arrives as a cell that collected rows
    # and published none -- 26,902 phantom orphans on an EAP build, and a
    # "loss" of half the corpus that is really just the region filter doing
    # its job.
    if countries is not None:
        df = df[df["country"].isin(countries)]
    df["coicop_code"] = df["coicop_code"].map(_normalize_coicop)
    df = df.dropna(subset=["coicop_code", "country"])
    keys = ["coicop_code", "country"]

    out: dict[str, pd.DataFrame] = {}
    for key, days in GRIDS.items():
        w = df[df["observation_date"] >= _window_cutoff(days)]
        g = w.groupby(keys).size().rename("n_total").reset_index()
        prod = (
            w.drop_duplicates(keys + ["product_name"])
            .groupby(keys)
            .size()
            .rename("n_products_total")
            .reset_index()
        )
        g = g.merge(prod, on=keys, how="left")

        nt = w[w["qa_status"] != "trusted"]
        if not nt.empty:
            g = g.merge(
                nt.groupby(keys).size().rename("n_lost_qa").reset_index(),
                on=keys, how="left",
            )
            g = g.merge(
                _top_reason(nt.groupby(keys + ["qa_status"]).size()),
                on=keys, how="left",
            )
            # Products that produced NO trusted row anywhere in the window, and
            # the reason most of their rows died. A product losing rows to two
            # different gates is rare beside one failing wholesale, so the
            # dominant reason is a fair label and a cheap one.
            tr_keys = (
                w[w["qa_status"] == "trusted"][keys + ["product_name"]]
                .drop_duplicates()
            )
            lost = nt.merge(tr_keys, on=keys + ["product_name"], how="left",
                            indicator=True)
            lost = lost[lost["_merge"] == "left_only"]
            if not lost.empty:
                g = g.merge(
                    lost.drop_duplicates(keys + ["product_name"])
                    .groupby(keys).size().rename("n_products_lost").reset_index(),
                    on=keys, how="left",
                )
                ptop = _top_reason(lost.groupby(keys + ["qa_status"]).size())
                ptop.columns = keys + ["top_qa_prod", "n_top_qa_prod"]
                g = g.merge(ptop, on=keys, how="left")
        for c in ("n_lost_qa", "n_top_qa", "n_products_lost", "n_top_qa_prod"):
            if c not in g:
                g[c] = 0
            g[c] = g[c].fillna(0).astype(int)
        for c in ("top_qa", "top_qa_prod"):
            if c not in g:
                g[c] = None
        logger.info(
            "funnel[%s]: %d collected rows / %d products over %d (leaf, country) "
            "pairs; %d rows rejected by QA",
            key,
            int(g["n_total"].sum()),
            int(g["n_products_total"].sum()),
            len(g),
            int(g["n_lost_qa"].sum()),
        )
        out[key] = g

    # Monthly collected counts, for the chart's pass-rate tooltip. Same loose
    # denominator as the cells, on (leaf, country, month) -- the grain the
    # series is drawn on.
    df["month"] = df["observation_date"].dt.to_period("M").dt.to_timestamp()
    out["_monthly"] = (
        df.groupby(keys + ["month"]).size().rename("n_total").reset_index()
    )
    out["_monthly_products"] = (
        df.drop_duplicates(keys + ["month", "product_name"])
        .groupby(keys + ["month"])
        .size()
        .rename("n_products_total")
        .reset_index()
    )
    del df
    return out


def _cell_key(code: str, unit: str) -> str:
    """Row identity for the heat table: a COICOP leaf measured in one unit."""
    return f"{code}|{unit}"


def _humanize_slug(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title()


def _current_snapshot(
    df: pd.DataFrame, days: int | None = CURRENT_LOOKBACK_DAYS
) -> pd.DataFrame:
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
    df = df[df["observation_date"] >= _window_cutoff(days)]
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


def _upstream_kpi(cur: pd.DataFrame) -> dict:
    """Classifier totals, and the collected figure for exactly those cells."""
    if "n_classified" not in cur:
        return {}
    up = cur[cur["n_classified"] > 0]
    if up.empty:
        return {}
    return {
        "classified": int(up["n_classified"].sum()),
        "decided": int(up["n_decided"].sum()),
        "collected_upstream": int(up["n_total"].sum()),
        "upstream_cells": int(len(up)),
    }


def _orphan_cells(published: pd.DataFrame, funnel: pd.DataFrame) -> pd.DataFrame:
    """(leaf, country) pairs that collected rows but published none.

    THE THINNEST CELLS ON THE PAGE, and until now the only ones it could not
    show: a cell is built from published rows, so a pair whose every row was
    rejected had nothing to hang a number on and simply vanished. It read as
    "we have no data here", when the truth was "we have data here and none of
    it survived" -- which is the opposite instruction to whoever works on
    sources.

    They take the leaf's display unit so they land in the row the leaf already
    has rather than opening a second one. A leaf with no published cell
    anywhere has no display unit to borrow and gets an empty one; that is 3
    rows out of 7,312 on the September 2026 corpus.
    """
    keys = ["coicop_code", "country"]
    have = published[keys].drop_duplicates()
    orphan = funnel.merge(have, on=keys, how="left", indicator=True)
    orphan = orphan[orphan["_merge"] == "left_only"].drop(columns="_merge")
    if orphan.empty:
        return orphan
    unit_of = (
        published.groupby("coicop_code")["standard_unit"].agg(lambda s: s.iloc[0])
        if not published.empty
        else pd.Series(dtype=object)
    )
    orphan = orphan.assign(
        standard_unit=orphan["coicop_code"].map(unit_of).fillna(""),
        median_usd=pd.NA,
        n_obs=0,
        n_products=0,
        n_imputed=0,
        imp_share=0.0,
        imputed=False,
        orphan=True,
        last_seen=pd.NaT,
    )
    logger.info(
        "%d orphan cells (collected but nothing published) carrying %d rows",
        len(orphan),
        int(orphan["n_total"].sum()),
    )
    return orphan


def _assemble_grid(
    published: pd.DataFrame,
    funnel: pd.DataFrame,
    unit_loss: pd.Series,
    prune_loss: pd.Series,
) -> pd.DataFrame:
    """One window's cells, each carrying where its observations went.

    The identity every cell satisfies:

        collected = published + lost_qa + lost_unit + lost_prune + lost_other

    `lost_other` is the residual, and it is kept rather than folded into the
    others precisely because it is the term nobody predicted. A non-zero
    residual means a row left the pipeline somewhere this function does not
    know about, and a page that silently absorbed it into "QA" would be
    reporting a fiction with the same confidence as a fact.
    """
    keys = ["coicop_code", "country"]
    published = published.copy()
    published["orphan"] = False
    grid = pd.concat(
        [published.merge(funnel, on=keys, how="left"),
         _orphan_cells(published, funnel)],
        ignore_index=True,
    )
    for name, series in (("n_lost_unit", unit_loss), ("n_lost_prune", prune_loss)):
        grid[name] = (
            pd.MultiIndex.from_frame(grid[keys]).map(series).to_numpy()
            if len(series)
            else 0
        )
        grid[name] = pd.Series(grid[name]).fillna(0).astype(int)
    for c in ("n_total", "n_products_total", "n_lost_qa", "n_top_qa",
              "n_products_lost", "n_top_qa_prod"):
        grid[c] = grid[c].fillna(0).astype(int)
    # A published cell always has at least its own rows behind it; if the
    # denominator came back smaller the join missed, and reporting a pass rate
    # above 100% is worse than reporting none.
    grid["n_total"] = grid[["n_total", "n_obs"]].max(axis=1)
    grid["n_products_total"] = grid[["n_products_total", "n_products"]].max(axis=1)
    grid["n_lost_other"] = (
        grid["n_total"] - grid["n_obs"] - grid["n_lost_qa"]
        - grid["n_lost_unit"] - grid["n_lost_prune"]
    ).clip(lower=0)
    resid = int(grid["n_lost_other"].sum())
    if resid:
        logger.info(
            "%d rows (%.2f%% of collected) left the pipeline outside the three "
            "measured stages; carried as lost_other",
            resid,
            100 * resid / max(int(grid["n_total"].sum()), 1),
        )
    return grid


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


def _attach_fills(monthly: pd.DataFrame, fills: pd.DataFrame) -> pd.DataFrame:
    """Append released fills to the monthly series, flagged, never merged.

    Same two rules the explorer uses: a fill may only extend a series that
    already exists on measured data, and it may never share a month with a drawn
    observation. `month` is a Timestamp here and a "YYYY-MM" string in the
    summary parquet, so the conversion happens once, at this boundary.
    """
    monthly = monthly.copy()
    monthly["imputed"] = False
    monthly["prob"] = np.nan
    if fills.empty or monthly.empty:
        return monthly

    f = fills.copy()
    f["month"] = pd.to_datetime(f["period"] + "-01")
    keys = ["coicop_code", "country", "month", "standard_unit"]
    live = monthly[["coicop_code", "country", "standard_unit"]].drop_duplicates()
    f = f.merge(live, on=["coicop_code", "country", "standard_unit"], how="inner")
    if f.empty:
        return monthly

    drawn = set(map(tuple, monthly[keys].astype(str).values))
    f = f[[tuple(r) not in drawn for r in f[keys].astype(str).values]]
    if f.empty:
        return monthly

    f = f.assign(median_usd=f["usd"], n_obs=0, imputed=True)[
        keys + ["median_usd", "n_obs", "imputed", "prob"]
    ]
    return pd.concat([monthly, f], ignore_index=True)


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
            n_products=("product_name", "nunique"),
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
                grp if col["key"] == "world" else grp.loc[grp["_region"].eq(col["key"])]
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
                imp[col["key"]] = round(float(sub.loc[have, "imp_share"].mean()), 4)
        key = _cell_key(code, unit)
        medians[key] = med
        counts[key] = cnt
        products[key] = prod
        shares[key] = imp
    return medians, counts, products, shares


def _source_provenance(path: Path) -> dict:
    """Which corpus file this page was built from, stated on the page itself.

    "Generated <timestamp>" says when the HTML was written, which is not the
    same question as which scrape it rests on -- a page regenerated today off
    a fortnight-old parquet looks identically fresh. So the corpus file's own
    mtime, size and row count travel into the payload and onto the page, in
    UTC and in US Eastern, because the collection cadence is reasoned about in
    Eastern and a UTC stamp silently lands on the following day for anything
    that finishes after 20:00.

    Row count comes from the parquet footer, so this is a stat and a metadata
    read -- it does not touch the data.
    """
    import pyarrow.parquet as pq

    st = path.stat()
    ts = pd.Timestamp(st.st_mtime, unit="s", tz="UTC")
    return {
        "name": path.name,
        "path": str(path.resolve()),
        "mtime_utc": ts.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "mtime_et": ts.tz_convert("America/New_York").strftime(
            "%a %Y-%m-%d %H:%M:%S %Z"
        ),
        "size_bytes": int(st.st_size),
        "rows": int(pq.ParquetFile(path).metadata.num_rows),
    }


def _region_obs(
    keyed: pd.DataFrame, region_cols: list[dict[str, str]]
) -> dict[str, dict[str, dict[str, int]]]:
    """Per (leaf, region): both metrics, both sides of the funnel, and breadth.

    The price view's region column is a median of country medians, so its `n`
    describes countries. Here the column is a SUM, so the two numbers answer
    different questions and both are returned: the total is the evidence, the
    country count is how concentrated it is. A leaf whose 40,000 observations
    all come from one country is not the same finding as one spread over
    twelve, and a total alone cannot tell them apart.
    """
    fields = ("obs", "obs_all", "prod", "prod_all", "n", "clf", "dec")
    out: dict[str, dict[str, dict[str, int]]] = {f: {} for f in fields}
    cols = {"obs": "n_obs", "obs_all": "n_total",
            "prod": "n_products", "prod_all": "n_products_total",
            "clf": "n_classified", "dec": "n_decided"}
    for (code, unit), grp in keyed.groupby(["coicop_code", "standard_unit"]):
        acc: dict[str, dict[str, int]] = {f: {} for f in fields}
        for col in region_cols:
            sub = (
                grp if col["key"] == "world" else grp.loc[grp["_region"].eq(col["key"])]
            )
            if sub.empty:
                continue
            for f, c in cols.items():
                if c in sub:
                    acc[f][col["key"]] = int(sub[c].sum())
            # Countries with a MEASURED observation, not countries with a cell:
            # a column of modelled-only or wholly-rejected cells would otherwise
            # report a breadth the zero total plainly contradicts.
            acc["n"][col["key"]] = int(sub.loc[sub["n_obs"] > 0, "country"].nunique())
        key = _cell_key(code, unit)
        for f in fields:
            out[f][key] = acc[f]
    return out


def _obs_labels(scope_label: str) -> dict[str, str]:
    """Page copy for the observation-count view.

    It lives in the payload rather than the template because the template is
    shared with the price view, and a page that says "median USD per unit"
    above a grid of counts is worse than no caption at all.
    """
    return {
        "page_title": f"{scope_label} price observations - coverage",
        "page_h1": f"{scope_label} — price observations per category and country",
        "sub_note": (
            "Every cell traces one (COICOP category x country) pair back "
            "through the pipeline: T trusted, O observations collected, D "
            "decided, C classified. Read right to left. C is every raw row "
            "the classifier scored for this category; D is the subset it "
            "resolved to a code, whether the model accepted it or the source "
            "declared a single leaf and short-circuited it; O is what reached "
            "the build; T is what the price dashboard draws. So 14 T 14 O and "
            "14 T 900 O are opposite findings about a source, and one number "
            "could never tell them apart. D and C appear on the all-time grid "
            "only: products_input "
            "is deduplicated with one collapsed date per row and the build "
            "re-dates the same rows, so a windowed classifier count would be "
            "precise and wrong. Rows reaching the build without a classifier "
            "record are not counted in D or C \u2014 57 rows in 20.1M across "
            "EAP. Hover any cell for where the missing rows went \u2014 "
            "below the classifier\u2019s confidence threshold, rejected by "
            "QA, dropped as an unconvertible unit, or pruned by RT-CAL as an "
            "implausible price. "
            "The {scope} column carries the same pair summed over the "
            "category, with n = the number of countries contributing a "
            "published observation. Catch-all COICOP categories "
            "(\u201cOther \u2026\u201d, \u201c\u2026 n.e.c.\u201d) are "
            "shown here though the price view hides them: counting rows is "
            "unit-free, so the comparability objection does not apply. Cells "
            "reading 0 (N) collected N rows and published NONE of them "
            "\u2014 the thinnest cells on the page, and ones the price view "
            "cannot show at all. Shading follows the PUBLISHED count on a "
            "shared log scale; pale = few, deep blue = many."
        ),
        "sub_note_hist": (
            "Monthly count per (COICOP leaf, country), on whichever metric is "
            "selected above. FX history starts {fxfloor} and earlier "
            "observations are excluded, so this is the priced corpus rather "
            "than the scrape; hover a point for the share of that month\u2019s "
            "collected rows that reached it. This chart is ALWAYS all-time \u2014 "
            "the window control applies to the table only, because cropping "
            "the history would hide whether a loss is recent or structural."
        ),
    }


def _coverage_cutoff(
    current: pd.DataFrame, residual: frozenset[str]
) -> tuple[int, set[str], dict]:
    """Countries whose COICOP breadth is below a FIXED floor, and the counts.

    Breadth is counted over named leaves only. A residual leaf is a catch-all,
    so crediting a country for reaching one would reward the classifier giving
    up rather than the country having a real price for a real category.

    THE CUT USED TO BE THE 25TH PERCENTILE, and a percentile is a filter that
    can never be satisfied: it removes a quarter of the countries however good
    they all become, and it has no opinion about how thin thin is. On this
    corpus it called Belgium, Kuwait, Norway, Iceland and Tanzania low-coverage
    alongside Gibraltar's single leaf, and it stranded Northern Mariana Islands
    one leaf below a boundary that was a fact about the other 201 countries.
    `COVERAGE_MIN_NAMED_LEAVES` is an absolute claim about the country instead:
    below it, a column is too empty to be worth a regional median's attention,
    and it stops being true the moment the country is collected properly.

    The count per country is returned with the set, because the toggle this
    feeds hides columns and a hidden column has to be able to say why.
    """
    named = current[~current["coicop_code"].isin(residual)]
    per_country = named.groupby("country")["coicop_code"].nunique()
    if per_country.empty:
        return (
            0,
            set(),
            {
                "median": 0,
                "n_countries": 0,
                "n_named_leaves": 0,
                "n_dropped": 0,
                "mode": "floor",
                "counts": {},
            },
        )
    threshold = COVERAGE_MIN_NAMED_LEAVES
    low = set(per_country.index[per_country < threshold])
    stats = {
        "median": int(per_country.median()),
        "n_countries": int(per_country.size),
        "n_named_leaves": int(named["coicop_code"].nunique()),
        "n_dropped": len(low),
        # An ABSOLUTE floor, said out loud, so the label on the toggle can stop
        # claiming a quartile. A client reading `mode` can print the right
        # sentence without having to know which release it is looking at.
        "mode": "floor",
        # Named leaves per country. This is what makes the toggle honest: the
        # reader can see how thin each hidden column actually is, and a future
        # slider can move the floor without a rebuild.
        "counts": {str(k): int(v) for k, v in per_country.items()},
    }
    return threshold, low, stats


# The imputation fields on a record that has none. The global dashboard's
# monthly array runs to millions of rows and the file is already ~90 MB, so
# three constant fields per row is tens of megabytes of "nothing was modelled
# here" -- which is what an absent key says for free. A client reading these
# must treat missing as false / zero, which is what `undefined` does in JS
# anyway.
_IMP_FIELDS = ("imputed", "imp_share", "n_imputed")


# Fields that mean "nothing happened here" when absent, which is what an
# omitted key already says for free. On the global build the loss columns are
# zero on most cells and the collected count equals the published one on most
# months, so writing them out in full adds tens of megabytes of "no".
_ZERO_DROP = ("n_lost_qa", "n_lost_unit", "n_lost_prune", "n_lost_other",
              "n_products_lost", "n_top_qa", "n_top_qa_prod",
              "n_classified", "n_decided")


def _lean(r: dict) -> dict:
    if not r.get("n_imputed"):
        r = {k: v for k, v in r.items() if k not in _IMP_FIELDS}
    # A denominator equal to its numerator is a 100% pass rate, which the
    # client can infer; only a REAL gap needs the bytes.
    if r.get("n_total") == r.get("n_obs"):
        r.pop("n_total", None)
    if r.get("n_products_total") == r.get("n_products"):
        r.pop("n_products_total", None)
    for k in _ZERO_DROP:
        if not r.get(k):
            r.pop(k, None)
    if "n_top_qa" not in r:
        r.pop("top_qa", None)
    if "n_top_qa_prod" not in r:
        r.pop("top_qa_prod", None)
    if not r.get("orphan"):
        r.pop("orphan", None)
    # NaN is a valid JS literal but not a value: it reaches the client as
    # `prob: NaN` on every measured point, which is 9 MB of nothing globally.
    if isinstance(r.get("prob"), float) and r["prob"] != r["prob"]:
        r.pop("prob", None)
    return r


def _payload(
    current: pd.DataFrame,
    monthly: pd.DataFrame,
    region: str | None = None,
    metric: str = "price",
    days: int | None = CURRENT_LOOKBACK_DAYS,
    include_monthly: bool = True,
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
    keyed_all = current.assign(_region=current["country"].map(of_country))
    keyed = keyed_all[~keyed_all["coicop_code"].isin(residual)]
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

    # OBS METRIC. Totals rather than medians, and over EVERY leaf including the
    # residuals. The reason a residual leaf's price median is withheld is that
    # "Other bakery products" is a different bag of goods in each country, so
    # the comparison is meaningless. Counting rows carries no such claim -- it
    # is unit-free and country-local -- so withholding it would hide real
    # coverage for a reason that does not apply.
    kept_all = keyed_all[~keyed_all["country"].isin(low_coverage)]
    region_obs = _region_obs(keyed_all, region_cols)
    region_obs_kept = _region_obs(kept_all, region_cols)

    shown = current[~current["coicop_code"].isin(residual)]
    shown_kept = shown[~shown["country"].isin(low_coverage)]

    def _kpi(cur: pd.DataFrame, shown: pd.DataFrame, n_countries: int) -> dict:
        live = cur[~cur.get("orphan", False)] if "orphan" in cur else cur
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
        out = {
            "countries": n_countries,
            # Breadth and country counts stay PUBLISHABLE-ONLY. An orphan cell
            # is the thinness the low-coverage cutoff exists to flag, so
            # crediting a country with breadth for one would let a column of
            # wholly-rejected cells argue its own way past the gate.
            "coicop_leaves": int(
                shown.loc[~shown.get("orphan", False), "coicop_code"].nunique()
                if "orphan" in shown else shown["coicop_code"].nunique()
            ),
            "products": int(live["n_products"].sum()),
            "observations": int(live["n_obs"].sum()),
            "cells": int(len(live)),
            "imputed_cells": int(live["imputed"].sum()),
        }
        if "n_total" in cur:
            out.update(
                collected=int(cur["n_total"].sum()),
                products_collected=int(cur["n_products_total"].sum()),
                lost_qa=int(cur["n_lost_qa"].sum()),
                lost_unit=int(cur["n_lost_unit"].sum()),
                lost_prune=int(cur["n_lost_prune"].sum()),
                lost_other=int(cur["n_lost_other"].sum()),
                # SUMMED OVER THE SAME CELLS, or the tiles compare different
                # populations: classified and decided exist only where the
                # upstream join was coherent, while collected exists
                # everywhere. Summing each over its own set put the global
                # headline at 30.3M decided against 31.1M collected -- a
                # negative loss that is pure aggregation artefact.
                **_upstream_kpi(cur),
                dead_cells=int(cur.get("orphan", pd.Series(False)).sum()),
                dead_cell_rows=int(cur.loc[cur.get("orphan", False), "n_total"].sum())
                if "orphan" in cur else 0,
            )
        return out

    kpi = _kpi(current, shown, len(country_display))
    kept_cur = current[~current["country"].isin(low_coverage)]
    kpi_kept = _kpi(kept_cur, shown_kept, len(country_display) - len(low_coverage))

    cutoff = None if days is None else _window_cutoff(days).date().isoformat()
    data_through = (
        pd.to_datetime(current["last_seen"], errors="coerce").max().date().isoformat()
        if not current.empty and current["last_seen"].notna().any()
        else None
    )
    if metric == "obs":
        # `data_through` above already read `last_seen`; the column itself is
        # per-cell and unused by the obs client, so it goes with the prices.
        # No price leaves this function in obs mode -- not in a cell, not in a
        # region column, not in a tooltip, and not sitting unread in the blob
        # either. A page that shows counts should not be shipping 750k medians
        # a reader could dig out of view-source, and dropping them takes ~25 MB
        # off the global file.
        current = current.drop(columns=["median_usd", "last_seen"], errors="ignore")
        monthly = monthly.drop(columns=["median_usd"], errors="ignore")
        region_medians = region_medians_kept = {}
        region_n_products = region_n_products_kept = {}
        region_imp = region_imp_kept = {}
    return {
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "source_parquet": _source_provenance(OBSERVATIONS_PARQUET),
        "trusted_parquet": (
            _source_provenance(TRUSTED_PARQUET) if TRUSTED_PARQUET.exists() else None
        ),
        "classifier": (
            {"name": HIERLEX_PRED_DIR.name, "windowed": False}
            if HIERLEX_PRED_DIR.exists() else None
        ),
        # True only in the diagnostic build. Carried in the payload as well as
        # in the banner, so a client can refuse to treat these numbers as
        # publishable rather than relying on the reader having seen a stripe.
        "unfiltered": UNFILTERED,
        "lookback_days": days,
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
        # Which number the cells carry. Absent/"price" is the historical
        # dashboard; "obs" swaps the value, the scale and the page copy and
        # changes nothing about which cells exist.
        "metric": metric,
        "region_obs": region_obs,
        "region_obs_kept": region_obs_kept,
        **(_obs_labels(region_cols[0]["label"] if region else "Global")
           if metric == "obs" else {}),
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
            "classified": "raw rows the classifier SCORED for this category, "
            "all-time. products_input dates are collapsed by dedup and do not "
            "match the build's, so this cannot be windowed",
            "decided": "of those, rows it resolved to a code -- accepted by "
            "the model, or short-circuited by a source that declared a single "
            "leaf. The gap to classified is what the classifier refused",
            "collected_upstream": "observations collected in the cells that "
            "carry a classifier count, so the two are comparable. Cells whose "
            "upstream figures ran backwards are excluded from all three",
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
        ] if include_monthly else [],
    }


def _render(payload: dict, chart_js: str) -> str:
    data_json = json.dumps(payload, default=str)
    template = HTML_TEMPLATE_PATH.read_text()
    return template.replace("/*__CHART_JS__*/", chart_js).replace(
        "/*__DATA__*/", data_json
    )


def publish(
    region: str | None = None,
    out_path: Path | None = None,
    metric: str = "price",
) -> Path:
    """Render the dashboard, optionally restricted to one region's countries.

    The restriction happens here, before `_to_display_units` and both
    aggregations run, so a region build is a genuinely separate computation
    over a smaller country set -- not the global numbers with columns hidden
    in the browser. Every downstream figure (KPIs, region/World medians, the
    low-coverage cutoff, the monthly series) is consistent with what is on
    screen.
    """
    if metric not in {"price", "obs"}:
        raise ValueError(f"unknown metric {metric!r}; expected 'price' or 'obs'")
    if not OBSERVATIONS_PARQUET.exists():
        raise FileNotFoundError(
            f"{OBSERVATIONS_PARQUET} not found — run `po prices build` first."
        )
    keep_countries = None
    if region is not None:
        _of_country, _region_order = _load_regions()
        if region not in {rc["key"] for rc in _region_order}:
            raise ValueError(f"unknown region {region!r} (see regions.yaml)")
        keep_countries = {c for c, r in _of_country.items() if r == region}
    funnel = (
        _loss_funnel(OBSERVATIONS_PARQUET, keep_countries)
        if metric == "obs" else None
    )
    classify = _classify_funnel(keep_countries) if metric == "obs" else None
    # UNFILTERED deliberately admits rows QA rejected, so it cannot start from
    # a frame those rows were already removed from.
    if UNFILTERED or not TRUSTED_PARQUET.exists():
        obs = _read_publish_columns(OBSERVATIONS_PARQUET)
    else:
        obs = _read_publish_columns(TRUSTED_PARQUET)
        logger.info("trusted frame read from %s", TRUSTED_PARQUET.name)
    obs["observation_date"] = pd.to_datetime(obs["observation_date"], errors="coerce")
    obs = obs[obs["observation_date"].notna()]
    if UNFILTERED:
        # THE ONE GATE IN THE DIAGNOSTIC BUILD THAT IS NOT ABOUT THIN EVIDENCE,
        # and the one most likely to put a nonsense number on the page. Every
        # other gate the profile lifts withholds a real figure for being thin;
        # this one withholds rows the QA layer judged WRONG -- a failed quantity
        # parse, a failed FX lookup, a unit value outside the plausible band. On
        # the September 2026 parquet it admits 3,725,851 extra rows on top of
        # 15,225,019 trusted ones, a 24.5% increase, and none of them have been
        # checked. It is lifted because "unfiltered" would otherwise be a
        # half-truth, and the banner says what that means.
        logger.warning(
            "UNFILTERED: qa_status filter lifted, %d rows of every status", len(obs)
        )
    elif "qa_status" in obs.columns:
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
    # Keys have to be stable across the three stage counts, and
    # `_to_display_units` normalises `coicop_code` itself -- so do it first and
    # count against the same spelling on both sides of every difference.
    obs["coicop_code"] = obs["coicop_code"].map(_normalize_coicop)
    stage_trusted = _stage_counts(obs) if metric == "obs" else {}
    obs = _to_display_units(obs)
    stage_unit = _stage_counts(obs) if metric == "obs" else {}
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
    stage_prune = _stage_counts(obs) if metric == "obs" else {}
    obs = _fill_rows(obs, _fold_piece_units(fills_mod.load_released_fills()))
    monthly = _attach_fills(
        _monthly_series(obs), _fold_piece_units(fills_mod.load_released_fills())
    )

    if metric != "obs":
        payload = _payload(
            _current_snapshot(obs), monthly, region=region, metric=metric
        )
    else:
        mk = ["coicop_code", "country", "month"]
        monthly = monthly.merge(funnel["_monthly"], on=mk, how="left")
        monthly = monthly.merge(funnel["_monthly_products"], on=mk, how="left")
        for c, floor in (("n_total", "n_obs"), ("n_products_total", "n_products")):
            monthly[c] = monthly[c].fillna(monthly[floor])
            monthly[c] = monthly[[c, floor]].max(axis=1).astype(int)
        grids: dict[str, pd.DataFrame] = {}
        for key, days in GRIDS.items():
            grids[key] = _assemble_grid(
                _current_snapshot(obs, days),
                funnel[key],
                stage_trusted[key].subtract(stage_unit[key], fill_value=0),
                stage_unit[key].subtract(stage_prune[key], fill_value=0),
            )
            if key == "all" and classify is not None:
                g = grids[key].merge(
                    classify, on=["coicop_code", "country"], how="left"
                )
                for c in ("n_classified", "n_decided"):
                    g[c] = g[c].fillna(0).astype(int)
                # THE FUNNEL MUST NOT RUN BACKWARDS. C and D count the same
                # rows at earlier stages, so C >= D >= O holds by construction
                # -- and where it does not, the cell's upstream figures are
                # attributed to a leaf the build disagrees with, not measured
                # wrong. Withhold both rather than publish a negative loss:
                # checking only C >= O let 559 global cells through and turned
                # the headline into "-727,751 rows never reached the build".
                has = g["n_classified"] > 0
                incoherent = has & (
                    (g["n_classified"] < g["n_decided"])
                    | (g["n_decided"] < g["n_total"])
                )
                bad = int(incoherent.sum())
                if bad:
                    logger.info(
                        "%d of %d cells with an upstream count had it running "
                        "backwards (C < D or D < collected); withheld there "
                        "rather than shown as a negative loss",
                        bad, int(has.sum()),
                    )
                    g.loc[incoherent, ["n_classified", "n_decided"]] = 0
                grids[key] = g
                logger.info(
                    "grid[all]: %d classified -> %d decided -> %d collected "
                    "(classifier rejected %d, %d more never reached the build)",
                    int(g["n_classified"].sum()), int(g["n_decided"].sum()),
                    int(g["n_total"].sum()),
                    int(g["n_classified"].sum() - g["n_decided"].sum()),
                    int(g["n_decided"].sum() - g["n_total"].sum()),
                )
            logger.info(
                "grid[%s]: %d cells (%d orphan), %d published of %d collected",
                key,
                len(grids[key]),
                int(grids[key]["orphan"].sum()),
                int(grids[key]["n_obs"].sum()),
                int(grids[key]["n_total"].sum()),
            )
        # One `_payload` per grid, then the per-grid parts lifted out. The
        # shared parts -- country names, COICOP titles, the monthly series,
        # provenance -- are identical by construction, so the "all" payload IS
        # the page and each grid contributes only what differs between them.
        built = {
            key: _payload(
                grids[key], monthly, region=region, metric=metric,
                days=GRIDS[key], include_monthly=(key == "all"),
            )
            for key in GRIDS
        }
        payload = built["all"]
        per_grid = ("current", "region_obs", "region_obs_kept", "kpi", "kpi_kept",
                    "low_coverage", "coverage_cutoff", "lookback_days",
                    "cutoff_date", "data_through")
        payload["grids"] = {
            key: {k: built[key][k] for k in per_grid} for key in GRIDS
        }
        payload["grid_order"] = [
            {"key": "all", "label": "All time"},
            {"key": "cur", "label": f"Last {CURRENT_LOOKBACK_DAYS} days"},
        ]
        payload["default_grid"] = "all"
        payload["qa_reasons"] = QA_REASONS
        # The grids carry the cells; a second flat copy would double the
        # largest array in the file to say the same thing twice.
        for k in per_grid:
            payload.pop(k, None)
    chart_js = VENDOR_CHART_JS.read_text()
    html = _render(payload, chart_js)

    out = out_path or DASHBOARD_HTML
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    # No-op unless this is the diagnostic build, in which case it raises rather
    # than shipping an unstamped page.
    stamp_unfiltered(out)
    logger.info("wrote %s (%d monthly cells)", out, len(monthly))
    return out


def run() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    publish()
