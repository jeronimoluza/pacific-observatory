"""Example fuel price fetcher — copy and adapt for new sources.

A fetcher is a function that:
  1. Receives `cutoff` (date) — the last observation date we already have
  2. Fetches new data from the source (API, HTML table, PDF, Excel, etc.)
  3. Returns a DataFrame with the required columns (or None if no new data)

The collect layer handles dedup and storage — the fetcher just returns raw data.

See docs/fuel/HOW_TO_ADD_NEW_FETCHER.md for the full guide.
"""

from datetime import date

import pandas as pd

from core.http import make_session


def fetch_source_name(cutoff: date) -> pd.DataFrame | None:
    """Fetch fuel prices from [Source Name] after `cutoff`.

    Args:
        cutoff: Only return observations with dates strictly after this.
                If this is the first run, cutoff will be a configured fallback date.

    Returns:
        DataFrame with columns:
            - observation_date (str, YYYY-MM-DD): When the price was observed
            - country (str): Country name (must match countries.yaml)
            - fuel_product (str): Raw product name as it appears in source
            - price_local (float): Price in local currency
            - currency (str): ISO 4217 currency code
            - source_key (str): Must match the source key in your YAML config
            - unit (str, optional): Unit of measurement, default "L" (liter)
            - subnational_area (str, optional): State/province
            - city (str, optional): City name
            - address (str, optional): Station address

        Or None / empty DataFrame if no new data.
    """
    session = make_session()

    # -- Step 1: Fetch data from source --
    # Common patterns:
    #   HTML table:  response = session.get(url); soup = BeautifulSoup(response.text, "lxml")
    #   JSON API:    response = session.get(api_url); data = response.json()
    #   PDF:         import pdfplumber; pdf = pdfplumber.open(BytesIO(response.content))
    #   Excel:       pd.read_excel(BytesIO(response.content))

    url = "https://example.gov/api/fuel-prices"
    response = session.get(url)
    response.raise_for_status()
    data = response.json()

    # -- Step 2: Parse into rows --
    rows = []
    for item in data.get("prices", []):
        obs_date = item["date"]  # Must be YYYY-MM-DD string

        # Skip rows we already have
        if date.fromisoformat(obs_date) <= cutoff:
            continue

        rows.append(
            {
                "observation_date": obs_date,
                "country": "Country Name",
                "fuel_product": item["product_name"],
                "price_local": float(item["price"]),
                "currency": "USD",
                "source_key": "xx_source_name",
                "unit": "L",
            }
        )

    if not rows:
        return None

    return pd.DataFrame(rows)
