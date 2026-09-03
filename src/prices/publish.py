"""Render the global retail-price dashboard from the build parquet.

Two views, one HTML file, vendored Chart.js inlined (WB intranet
blocks cdn.jsdelivr.net):
  - Current snapshot: COICOP-leaf country heat table of median USD/unit
    from the dedup'd snapshot.
  - Historical: per-COICOP-leaf line chart of monthly USD/unit medians,
    one line per country, gated to 2024-03-06+ (FX coverage floor).

The unit-value grain is `coicop_code` (the deepest leaf the classifier
assigns); the retired cascade's `sub_label_id` sub-grain is no longer
produced, so each COICOP leaf is one row/series.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pandas as pd
import yaml

from prices.build.sold_by_item import SOLD_BY_ITEM_LEAVES

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


def _cell_key(code: str, unit: str) -> str:
    """Row identity for the heat table: a COICOP leaf measured in one unit."""
    return f"{code}|{unit}"


def _humanize_slug(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title()


def _current_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate observations within the last CURRENT_LOOKBACK_DAYS to a
    (coicop_code, country, standard_unit) median. Rows without a parseable
    observation_date are excluded.

    standard_unit is part of the grain, not a label picked off the first row:
    a leaf such as "Other condiments and sauces" holds both kg products (a
    jar of XO sauce) and lt products (a bottle of soy sauce), and a median
    taken across the two describes neither.
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
            n_obs=("unit_value_usd", "size"),
            last_seen=("observation_date", "max"),
        )
        .reset_index()
    )
    return g[g["n_obs"] >= MIN_OBS_PER_CELL]


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
            n_obs=("unit_value_usd", "size"),
        )
        .reset_index()
    )
    return g[g["n_obs"] >= MIN_OBS_PER_CELL]


def _payload(current: pd.DataFrame, monthly: pd.DataFrame) -> dict:
    coicop_titles = _load_coicop_titles()
    country_names = _load_country_names()

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

    # Median of country-level medians per (coicop leaf, unit), one entry per
    # region plus "world" (each country one observation, unweighted). Keyed on
    # the unit as well as the leaf: a kg column and an lt column measure
    # different things, so one median spanning both compares nothing.
    of_country, region_order = _load_regions()
    region_cols = [{"key": "world", "label": "World"}] + region_order
    region_medians: dict[str, dict[str, float]] = {}
    region_n_countries: dict[str, dict[str, int]] = {}
    keyed = current.assign(_region=current["country"].map(of_country))
    for (code, unit), grp in keyed.groupby(["coicop_code", "standard_unit"]):
        med: dict[str, float] = {}
        cnt: dict[str, int] = {}
        for col in region_cols:
            s = (
                grp["median_usd"]
                if col["key"] == "world"
                else grp.loc[grp["_region"].eq(col["key"]), "median_usd"]
            )
            n = int(s.notna().sum())
            if n:
                med[col["key"]] = float(s.median())
                cnt[col["key"]] = n
        key = _cell_key(code, unit)
        region_medians[key] = med
        region_n_countries[key] = cnt

    kpi = {
        "countries": len(country_display),
        "coicop_leaves": int(current["coicop_code"].nunique()),
        "products": int(current["n_obs"].sum()),
    }

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
        "kpi": kpi,
        "current": current.to_dict(orient="records"),
        "monthly": [
            {**r, "month": r["month"].date().isoformat()}
            for r in monthly.to_dict(orient="records")
        ],
    }


def _render(payload: dict, chart_js: str) -> str:
    data_json = json.dumps(payload, default=str)
    template = HTML_TEMPLATE_PATH.read_text()
    return template.replace("/*__CHART_JS__*/", chart_js).replace(
        "/*__DATA__*/", data_json
    )


def publish() -> Path:
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
    current = _current_snapshot(obs)
    monthly = _monthly_series(obs)

    payload = _payload(current, monthly)
    chart_js = VENDOR_CHART_JS.read_text()
    html = _render(payload, chart_js)

    DASHBOARD_HTML.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_HTML.write_text(html)
    logger.info(
        "wrote %s (%d current cells, %d monthly cells)",
        DASHBOARD_HTML,
        len(current),
        len(monthly),
    )
    return DASHBOARD_HTML


def run() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    publish()
