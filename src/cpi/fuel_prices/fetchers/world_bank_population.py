"""World Bank population fetcher — SP.POP.TOTL indicator, 2024."""

from pathlib import Path

import pandas as pd

from ..utils import get_session

SOURCE_META = [
    {
        "fetcher_fn": "fetch_wb_population",
        "country": "All countries (ancillary)",
        "source_name": "World Bank Total Population",
        "url": "https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL",
        "description": "Official multilateral institution (World Bank Open Data). Total population figures via a free documented REST API. Ancillary reference data used to compute per-capita subsidy values.",
        "extraction_method": ["REST API"],
        "products": ["Total population (ancillary reference data)"],
        "frequency": "Annual",
        "source_keys": [],
        "publishes_on": "Annual",
        "output": "population.csv",
        "notes": "Paginated API; returns most recent value (mrv=1) for all countries. Note: API returns absolute values, not thousands-rounded values shown on website.",
    },
]

_WB_API_URL = (
    "https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL"
    "?format=json&mrv=1&per_page=500&page={page}"
)

_OUTPUT_PATH = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "cpi"
    / "fuel_prices"
    / "population.csv"
)


def fetch_wb_population(year: int = 2024) -> pd.DataFrame:
    """Fetch World Bank total population (SP.POP.TOTL) for *year*.

    The WB REST API returns absolute values (not thousands).
    The website display rounds to thousands — those values are *not* used here.

    Returns
    -------
    pd.DataFrame
        Columns: country_name, wb_iso3, year, population
    """
    print(f"  [wb_population] Fetching SP.POP.TOTL for year={year} ...")
    session = get_session()
    records: list[dict] = []
    page = 1

    while True:
        url = _WB_API_URL.format(page=page)
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            print(f"  [wb_population] Error on page {page}: {e}")
            break

        if not isinstance(payload, list) or len(payload) < 2:
            print(f"  [wb_population] Unexpected response structure on page {page}")
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
        print(f"  [wb_population] Page {page}/{total_pages} — {len(data)} items")
        if page >= total_pages:
            break
        page += 1

    df = pd.DataFrame(
        records, columns=["country_name", "wb_iso3", "year", "population"]
    )
    df = df.sort_values("country_name").reset_index(drop=True)
    print(f"  [wb_population] Done — {len(df)} countries with {year} data")
    return df


if __name__ == "__main__":
    df = fetch_wb_population(year=2024)
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(_OUTPUT_PATH, index=False)
    print(f"  [wb_population] Saved {len(df)} rows to {_OUTPUT_PATH}")
