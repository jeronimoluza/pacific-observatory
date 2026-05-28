"""Text pipeline status computation and cache management."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_PATH = Path("data/.po_cache.json")
DATA_BASE = Path("data/text")
OUTPUTS_BASE = Path("outputs/text")
CONFIGS_DIR = Path(__file__).resolve().parent / "configs"


def read_status_cache(cache_path: Path = CACHE_PATH) -> dict | None:
    """Read po status cache from disk. Returns None if missing."""
    try:
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def write_status_cache(data: dict, cache_path: Path = CACHE_PATH) -> None:
    """Write po status cache to disk."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def compute_text_status() -> dict:
    """Scan data/text/ and outputs/text/ to compute text pipeline health."""
    import pandas as pd

    from core.config import discover_pipeline_configs, parse_config_path

    configs = discover_pipeline_configs(CONFIGS_DIR)
    sources_total = len(configs)

    config_countries = set()
    for c in configs:
        _, _, ctry = parse_config_path(c, CONFIGS_DIR)
        if ctry != "unknown":
            config_countries.add(ctry)

    sources_scraped = 0
    articles_total = 0
    date_earliest = None
    date_latest = None
    latest_mtime = None

    for news_csv in sorted(DATA_BASE.rglob("news.csv")):
        try:
            df = pd.read_csv(news_csv, usecols=["date"], dtype=str)
            if df.empty:
                continue
            sources_scraped += 1
            articles_total += len(df)
            dates = df["date"].dropna()
            if not dates.empty:
                file_min = dates.min()[:10]
                file_max = dates.max()[:10]
                if date_earliest is None or file_min < date_earliest:
                    date_earliest = file_min
                if date_latest is None or file_max > date_latest:
                    date_latest = file_max
            mtime = datetime.fromtimestamp(news_csv.stat().st_mtime, tz=timezone.utc)
            if latest_mtime is None or mtime > latest_mtime:
                latest_mtime = mtime
        except Exception:
            continue

    last_scraped_at = None
    if latest_mtime:
        delta = datetime.now(tz=timezone.utc) - latest_mtime
        days, hours = delta.days, delta.seconds // 3600
        last_scraped_at = f"{days}d {hours}h ago" if days > 0 else f"{hours}h ago"

    epu_files = list(OUTPUTS_BASE.rglob("epu.csv"))
    epu_count = len(epu_files)
    epu_latest_mtime = None
    for epu_csv in epu_files:
        try:
            mtime = datetime.fromtimestamp(epu_csv.stat().st_mtime, tz=timezone.utc)
            if epu_latest_mtime is None or mtime > epu_latest_mtime:
                epu_latest_mtime = mtime
        except Exception:
            continue

    last_built_at = epu_latest_mtime.strftime("%Y-%m-%d") if epu_latest_mtime else None

    dash_data = OUTPUTS_BASE / "dashboard_data" / "dashboard_data.json"
    dash_html = OUTPUTS_BASE / "small_dashboard_integrated.html"
    dash_data_exists = dash_data.exists()
    dash_html_exists = dash_html.exists()

    pub_mtime = None
    for f in [dash_data, dash_html]:
        if f.exists():
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if pub_mtime is None or mtime > pub_mtime:
                pub_mtime = mtime

    last_published_at = pub_mtime.strftime("%Y-%m-%d") if pub_mtime else None

    return {
        "collect": {
            "sources_total": sources_total,
            "sources_scraped": sources_scraped,
            "articles_total": articles_total,
            "countries_total": len(config_countries),
            "date_earliest": date_earliest,
            "date_latest": date_latest,
            "last_scraped_at": last_scraped_at,
        },
        "build": {
            "epu_outputs": epu_count,
            "last_built_at": last_built_at,
        },
        "publish": {
            "dashboard_data": dash_data_exists,
            "dashboard_html": dash_html_exists,
            "last_published_at": last_published_at,
        },
    }
