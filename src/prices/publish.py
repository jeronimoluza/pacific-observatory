"""Render the EAP F&B PoC dashboard from the build parquet.

Two views, one HTML file, vendored Chart.js inlined (WB intranet
blocks cdn.jsdelivr.net):
  - Current snapshot: COICOP-grouped country × sub_label heat table
    of median USD/unit from the dedup'd snapshot.
  - Historical: per-sub_label line chart of monthly USD/unit medians,
    one line per country, gated to 2024-03-06+ (FX coverage floor).
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pandas as pd
import yaml

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_DIR = REPO_ROOT / "data" / "prices" / "_build"
OBSERVATIONS_PARQUET = BUILD_DIR / "eap_fnb_observations.parquet"
VENDOR_CHART_JS = (
    REPO_ROOT / "src" / "text" / "plotting" / "vendor" / "chart.umd.min.js"
)
HTML_TEMPLATE_PATH = Path(__file__).resolve().parent / "_publish_template.html"
DASHBOARD_HTML = REPO_ROOT / "outputs" / "prices" / "eap_fnb_dashboard.html"
COICOP_XLSX = REPO_ROOT / "data" / "prices" / "_enrich" / "coicop_categories.xlsx"
COICOP_SUBCATS_JSON = (
    REPO_ROOT / "src" / "prices" / "enrich" / "static" / "coicop_subcategories.json"
)
COUNTRIES_YAML = REPO_ROOT / "src" / "configs" / "countries.yaml"

CURRENT_LOOKBACK_DAYS = 60
FX_HISTORY_FLOOR = pd.Timestamp("2024-03-06")
MIN_OBS_PER_CELL = 1
# Only rows whose trust_level is in this set reach the published dashboard.
# Cache rows without trust_level (legacy v1-era) are coalesced to "high" by
# the build stage, so this default is conservative without dropping vetted data.
PUBLISH_TRUST_LEVELS = frozenset({"high"})

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


def _load_sub_label_labels() -> dict[tuple[str, str], str]:
    if not COICOP_SUBCATS_JSON.exists():
        return {}
    raw = json.loads(COICOP_SUBCATS_JSON.read_text())
    out: dict[tuple[str, str], str] = {}
    for code, entries in raw.items():
        for e in entries:
            out[(code, e["id"])] = e["label"]
    return out


def _load_country_names() -> dict[str, str]:
    if not COUNTRIES_YAML.exists():
        return {}
    data = yaml.safe_load(COUNTRIES_YAML.read_text()) or {}
    return {slug: meta.get("name", slug) for slug, meta in data.items()}


def _humanize_slug(slug: str) -> str:
    if slug == "_other":
        return "Other"
    return slug.replace("-", " ").replace("_", " ").strip().title()


def _current_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate observations within the last CURRENT_LOOKBACK_DAYS to a
    (coicop_code, sub_label, country) median. Rows without a parseable
    observation_date are excluded.
    """
    df = df.copy()
    df["coicop_code"] = df["coicop_code"].map(_normalize_coicop)
    df = df[df["sub_label_id"] != "_other"]
    cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=CURRENT_LOOKBACK_DAYS)
    df = df[df["observation_date"] >= cutoff]
    g = (
        df.dropna(subset=["unit_value_usd", "sub_label_id", "coicop_code"])
        .groupby(["coicop_code", "sub_label_id", "country"])
        .agg(
            median_usd=("unit_value_usd", "median"),
            n_obs=("unit_value_usd", "size"),
            standard_unit=("standard_unit", "first"),
            last_seen=("observation_date", "max"),
        )
        .reset_index()
    )
    return g[g["n_obs"] >= MIN_OBS_PER_CELL]


def _monthly_series(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["observation_date"] >= FX_HISTORY_FLOOR].copy()
    sub = sub.dropna(subset=["unit_value_usd", "sub_label_id"])
    sub["month"] = sub["observation_date"].dt.to_period("M").dt.to_timestamp()
    g = (
        sub.groupby(["sub_label_id", "country", "month"])
        .agg(
            median_usd=("unit_value_usd", "median"),
            n_obs=("unit_value_usd", "size"),
            standard_unit=("standard_unit", "first"),
        )
        .reset_index()
    )
    return g[g["n_obs"] >= MIN_OBS_PER_CELL]


def _payload(current: pd.DataFrame, monthly: pd.DataFrame) -> dict:
    coicop_titles = _load_coicop_titles()
    sub_label_labels = _load_sub_label_labels()
    country_names = _load_country_names()

    used_countries = sorted(
        set(current["country"].unique())
        | (set(monthly["country"].unique()) if not monthly.empty else set())
    )
    country_display = {
        c: country_names.get(c, _humanize_slug(c)) for c in used_countries
    }

    # Hierarchy titles for all ancestor levels of codes we actually display
    coicop_used: dict[str, str] = {}
    for code in current["coicop_code"].dropna().unique():
        parts = str(code).split(".")
        for i in range(1, len(parts) + 1):
            anc = ".".join(parts[:i])
            if anc in coicop_titles:
                coicop_used[anc] = coicop_titles[anc]

    # Sub-label label per (coicop_code, sub_label_id) pair in the snapshot
    sub_labels_used: dict[str, dict[str, str]] = {}
    pairs = (
        current[["coicop_code", "sub_label_id"]]
        .drop_duplicates()
        .itertuples(index=False)
    )
    for code, sub in pairs:
        label = sub_label_labels.get((code, sub)) or _humanize_slug(sub)
        sub_labels_used.setdefault(code, {})[sub] = label

    # Regional (EAP) median per (coicop_code, sub_label_id) — median of
    # country-level medians (each country one observation, unweighted).
    region_medians: dict[str, dict[str, float]] = {}
    region_n_countries: dict[str, dict[str, int]] = {}
    grouped = current.groupby(["coicop_code", "sub_label_id"])["median_usd"]
    for (code, sub), s in grouped:
        region_medians.setdefault(code, {})[sub] = float(s.median())
        region_n_countries.setdefault(code, {})[sub] = int(s.notna().sum())

    kpi = {
        "countries": len(country_display),
        "coicop_leaves": int(current["coicop_code"].nunique()),
        "sub_labels": int(
            current[["coicop_code", "sub_label_id"]].drop_duplicates().shape[0]
        ),
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
        "sub_labels": sub_labels_used,
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
    if "trust_level" in obs.columns:
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
