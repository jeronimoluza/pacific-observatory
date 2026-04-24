"""World Bank GDP per capita loader (NY.GDP.PCAP.CD, current USD).

Fetches the most recent observation >= min_year for each country.
Cached to ``{cache_dir}/worldbank/gdp_per_capita.csv``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_WB_API_URL = (
    "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.CD"
    "?format=json&mrv=5&per_page=1000&page={page}"
)

_MIN_YEAR = 2022
_STALE_DAYS = 30


def _fetch_gdp(min_year: int = _MIN_YEAR) -> pd.DataFrame:
    """Fetch WB GDP per capita from API. Returns DataFrame or empty."""
    logger.info("Fetching WB NY.GDP.PCAP.CD (mrv=5, min_year=%d) ...", min_year)
    session = make_session()
    raw: list[dict] = []
    page = 1

    while True:
        url = _WB_API_URL.format(page=page)
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            logger.warning("Error on page %d: %s", page, e)
            break

        if not isinstance(payload, list) or len(payload) < 2:
            logger.warning("Unexpected response on page %d", page)
            break

        meta = payload[0]
        data = payload[1]
        if not data:
            break

        for item in data:
            value = item.get("value")
            year_str = item.get("date")
            country_name = item.get("country", {}).get("value")
            wb_iso3 = item.get("countryiso3code")
            if value is None or not wb_iso3 or not year_str:
                continue
            try:
                year = int(year_str)
            except (ValueError, TypeError):
                continue
            if year < min_year:
                continue
            raw.append(
                {
                    "country_name": country_name,
                    "wb_iso3": wb_iso3,
                    "year": year,
                    "gdp_per_capita": float(value),
                }
            )

        total_pages = meta.get("pages", 1)
        logger.info("Page %d/%d — %d items", page, total_pages, len(data))
        if page >= total_pages:
            break
        page += 1

    if not raw:
        logger.warning("No GDP data retrieved")
        return pd.DataFrame()

    df = pd.DataFrame(raw)
    df = df.sort_values(["wb_iso3", "year"], ascending=[True, False])
    df = df.drop_duplicates(subset=["wb_iso3"], keep="first")
    df = df.sort_values("country_name").reset_index(drop=True)
    logger.info("Done — %d countries", len(df))
    return df


def load_gdp(cache_dir: Path, min_year: int = _MIN_YEAR) -> pd.DataFrame:
    """Load GDP per capita, fetching from WB API if cache is missing or stale."""
    cache_path = cache_dir / "worldbank" / "gdp_per_capita.csv"
    if cache_path.exists():
        from datetime import datetime, timezone

        age_days = (
            datetime.now(timezone.utc)
            - datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc)
        ).days
        if age_days < _STALE_DAYS:
            logger.info("Using cached GDP data (%d days old)", age_days)
            return pd.read_csv(cache_path, low_memory=False)

    df = _fetch_gdp(min_year=min_year)
    if not df.empty:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache_path, index=False)
        logger.info("Saved %d rows to %s", len(df), cache_path)
    elif cache_path.exists():
        logger.warning("Fetch returned empty — using stale cache")
        return pd.read_csv(cache_path, low_memory=False)
    return df
