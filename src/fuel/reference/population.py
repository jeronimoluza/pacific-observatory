"""World Bank total population loader (SP.POP.TOTL).

Cached to ``{cache_dir}/worldbank/population.csv``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_WB_API_URL = (
    "https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL"
    "?format=json&mrv=1&per_page=500&page={page}"
)

_STALE_DAYS = 30


def _fetch_population(year: int = 2024) -> pd.DataFrame:
    """Fetch WB population from API. Returns DataFrame or empty."""
    logger.info("Fetching SP.POP.TOTL for year=%d ...", year)
    session = make_session()
    records: list[dict] = []
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
            obs_year = item.get("date")
            country_name = item.get("country", {}).get("value")
            wb_iso3 = item.get("countryiso3code")
            if value is None or not wb_iso3:
                continue
            if obs_year != str(year):
                continue
            records.append(
                {
                    "country_name": country_name,
                    "wb_iso3": wb_iso3,
                    "year": int(obs_year),
                    "population": int(round(value)),
                }
            )

        total_pages = meta.get("pages", 1)
        logger.info("Page %d/%d — %d items", page, total_pages, len(data))
        if page >= total_pages:
            break
        page += 1

    df = pd.DataFrame(
        records, columns=["country_name", "wb_iso3", "year", "population"]
    )
    df = df.sort_values("country_name").reset_index(drop=True)
    logger.info("Done — %d countries with %d data", len(df), year)
    return df


def load_population(cache_dir: Path, year: int = 2024) -> pd.DataFrame:
    """Load population data, fetching from WB API if cache is missing or stale."""
    cache_path = cache_dir / "worldbank" / "population.csv"
    if cache_path.exists():
        from datetime import datetime, timezone

        age_days = (
            datetime.now(timezone.utc)
            - datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc)
        ).days
        if age_days < _STALE_DAYS:
            logger.info("Using cached population data (%d days old)", age_days)
            return pd.read_csv(cache_path, low_memory=False)

    df = _fetch_population(year=year)
    if not df.empty:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache_path, index=False)
        logger.info("Saved %d rows to %s", len(df), cache_path)
    elif cache_path.exists():
        logger.warning("Fetch returned empty — using stale cache")
        return pd.read_csv(cache_path, low_memory=False)
    return df
