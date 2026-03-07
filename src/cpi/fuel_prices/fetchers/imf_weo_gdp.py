"""GDP per capita fetcher — World Bank API (NY.GDP.PCAP.CD, current USD).

Uses the World Bank REST API, same pattern as world_bank_population.py.
Fetches the most-recently-available year (mrv=1), typically 2023 or 2024
depending on country reporting lag. Requests up to 5 recent values (mrv=5)
and returns the most recent year >= min_year for each country.

Source: World Bank Open Data — https://data.worldbank.org/indicator/NY.GDP.PCAP.CD
"""

from pathlib import Path

import pandas as pd

from ..utils import get_session

_WB_API_URL = (
    "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.CD"
    "?format=json&mrv=5&per_page=1000&page={page}"
)

_OUTPUT_PATH = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "cpi"
    / "fuel_prices"
    / "gdp_per_capita.csv"
)

_MIN_YEAR = 2022


def fetch_imf_weo_gdp(min_year: int = _MIN_YEAR) -> pd.DataFrame:
    """Fetch World Bank GDP per capita (NY.GDP.PCAP.CD, current USD).

    Returns the most recent observation >= *min_year* for each country.

    Returns
    -------
    pd.DataFrame
        Columns: country_name, wb_iso3, year, gdp_per_capita
    """
    print(
        f"  [imf_weo_gdp] Fetching WB NY.GDP.PCAP.CD (mrv=5, min_year={min_year}) ..."
    )
    session = get_session()
    raw: list[dict] = []
    page = 1

    while True:
        url = _WB_API_URL.format(page=page)
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            print(f"  [imf_weo_gdp] Error on page {page}: {e}")
            break

        if not isinstance(payload, list) or len(payload) < 2:
            print(f"  [imf_weo_gdp] Unexpected response on page {page}")
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
        print(f"  [imf_weo_gdp] Page {page}/{total_pages} — {len(data)} items")
        if page >= total_pages:
            break
        page += 1

    if not raw:
        print("  [imf_weo_gdp] No data retrieved")
        return pd.DataFrame()

    df = pd.DataFrame(raw)
    df = df.sort_values(["wb_iso3", "year"], ascending=[True, False])
    df = df.drop_duplicates(subset=["wb_iso3"], keep="first")
    df = df.sort_values("country_name").reset_index(drop=True)
    print(
        f"  [imf_weo_gdp] Done — {len(df)} countries, years: {df['year'].value_counts().to_dict()}"
    )
    return df


if __name__ == "__main__":
    df = fetch_imf_weo_gdp()
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(_OUTPUT_PATH, index=False)
    print(f"  [imf_weo_gdp] Saved {len(df)} rows to {_OUTPUT_PATH}")
