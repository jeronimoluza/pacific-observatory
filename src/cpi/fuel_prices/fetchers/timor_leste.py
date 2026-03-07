"""Timor-Leste ANP daily fuel price fetcher."""

import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from ..utils import get_session, make_hash, make_template

_TMPL_TL = make_template(
    country="Timor-Leste",
    wb_iso3="TLS",
    source_key="tl_anp_daily_fuel_price",
    source_name="Timor-Leste ANP Daily Fuel Price",
    source_url="https://www.anp.tl/daily-fuel-price/",
    currency="USD",
    unit="L",
    subnational_area="National",
    publication_frequency="daily",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_TL_PRODUCTS = [
    ("Petrol", "gasoline", "regular", None, r"(?i)petrol|gasoline|benzina"),
    ("Diesel", "diesel", "regular", None, r"(?i)diesel|gasoleo"),
]


def fetch_timor_anp(cutoff: date) -> pd.DataFrame:
    """Fetch Timor-Leste ANP daily fuel prices (national average of station prices)."""
    print("  [tl_anp] Fetching Timor-Leste ANP data...")
    print(f"  [tl_anp] Cutoff: {cutoff}")

    session = get_session()
    url = "https://www.anp.tl/daily-fuel-price/"

    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [tl_anp] Could not fetch page: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")
    text = soup.get_text(separator="\n")

    obs_date = None
    iso_matches = re.findall(r"(20\d{2})[/\-](\d{2})[/\-](\d{2})", text)
    date_matches = re.findall(r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](20\d{2})", text)

    if iso_matches:
        try:
            obs_date = date(
                int(iso_matches[0][0]), int(iso_matches[0][1]), int(iso_matches[0][2])
            )
        except ValueError:
            pass
    elif date_matches:
        try:
            obs_date = date(
                int(date_matches[0][2]),
                int(date_matches[0][1]),
                int(date_matches[0][0]),
            )
        except ValueError:
            pass

    if obs_date is None:
        obs_date = date.today()
        print(f"  [tl_anp] No date found on page, using today: {obs_date}")
    else:
        print(f"  [tl_anp] Effective date from page: {obs_date}")

    if obs_date <= cutoff:
        print(f"  [tl_anp] Date {obs_date} not newer than cutoff {cutoff}, skipping")
        return pd.DataFrame()

    all_rows = []

    for table in soup.find_all("table"):
        rows_html = table.find_all("tr")
        if len(rows_html) < 3:
            continue
        headers = [
            c.get_text(strip=True).lower() for c in rows_html[0].find_all(["th", "td"])
        ]

        for prod_name, family, qg, ron, prod_pat in _TL_PRODUCTS:
            price_col = next(
                (i for i, h in enumerate(headers) if re.search(prod_pat, h)), None
            )
            if price_col is None:
                continue

            prices = []
            for row in rows_html[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                if price_col >= len(cells):
                    continue
                try:
                    p = float(re.sub(r"[^0-9.]", "", cells[price_col]))
                    if 0.5 <= p <= 5.0:
                        prices.append(p)
                except (ValueError, TypeError):
                    pass

            if not prices:
                continue

            avg_price = round(sum(prices) / len(prices), 4)
            r = _TMPL_TL.copy()
            r.update(
                {
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "price_local": avg_price,
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date),
                    "observation_date": str(obs_date),
                    "source_url": url,
                    "notes": f"National average of {len(prices)} station prices",
                }
            )
            r["observation_hash"] = make_hash(r)
            all_rows.append(r)
            print(
                f"  [tl_anp] {prod_name}: avg {avg_price:.4f} USD/L ({len(prices)} stations) on {obs_date}"
            )

    if not all_rows:
        # Fallback: plain text extraction
        for prod_name, family, qg, ron, prod_pat in _TL_PRODUCTS:
            pattern = rf"{prod_pat}[^\d]{{0,80}}(\d+\.\d{{2,3}})"
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            prices = [float(p) for p in matches if 0.5 <= float(p) <= 5.0]
            if prices:
                avg_price = round(sum(prices) / len(prices), 4)
                r = _TMPL_TL.copy()
                r.update(
                    {
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "price_local": avg_price,
                        "effective_from": str(obs_date),
                        "effective_to": str(obs_date),
                        "observation_date": str(obs_date),
                        "source_url": url,
                    }
                )
                r["observation_hash"] = make_hash(r)
                all_rows.append(r)

    if all_rows:
        print(f"  [tl_anp] {len(all_rows)} new rows")
    else:
        print("  [tl_anp] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
