"""Thailand EPPO NGV retail prices, Bangkok (monthly HTML table).

Ported unchanged from legacy pacific-observatory
``src/cpi/fuel_prices/fetchers/thailand.py::fetch_thailand_eppo_ngv`` (dev 2d60a353).
"""

import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from fuel.fetchers._shared.eap.legacy import get_session, make_hash, make_template
from fuel.fetchers._shared.eap.thailand import _parse_price_value

# ── EPPO NGV Bangkok ──────────────────────────────────────────────────────────

# EPPO's 2026 rebuild deleted the retail-priceNGV spreadsheet (404). The same
# Bangkok monthly NGV series now lives in an HTML table on the NGV price page,
# one row per year (Buddhist era, with the AD year in parentheses) and twelve
# monthly Baht/Kg columns.
_NGV_URL = (
    "https://www.eppo.go.th/data-energy-statistic/energy-price-th/"
    "%e0%b8%a3%e0%b8%b2%e0%b8%84%e0%b8%b2-ngv/"
)

# "2569 (2026)" -> 2026; the parenthesised AD year is the reliable token.
_NGV_YEAR_RE = re.compile(r"\((\d{4})\)")

_TMPL_TH_NGV = make_template(
    country="Thailand",
    wb_iso3="THA",
    source_key="th_eppo_ngv_bangkok_2025",
    source_name="Thailand EPPO NGV Retail Prices — Bangkok",
    source_url=_NGV_URL,
    currency="THB",
    unit="kg",
    subnational_area="Bangkok",
    publication_frequency="monthly",
    observation_method="reported",
    fuel_product="NGV retail price",
    fuel_family="natural_gas",
    quality_group="regular",
)


def fetch_thailand_eppo_ngv(cutoff: date) -> pd.DataFrame:
    """Fetch Thailand EPPO NGV retail prices from Bangkok (monthly HTML table)."""
    print("  [th_eppo_ngv] Fetching Thailand EPPO NGV data...")
    print(f"  [th_eppo_ngv] Cutoff: {cutoff}")

    session = get_session()
    try:
        resp = session.get(_NGV_URL, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [th_eppo_ngv] Could not fetch page: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")
    table = None
    for candidate in soup.find_all("table"):
        if "Baht/Kg" in candidate.get_text(" ", strip=True):
            table = candidate
            break
    if table is None:
        print("  [th_eppo_ngv] No Baht/Kg table on page")
        return pd.DataFrame()

    all_rows = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if not cells:
            continue
        year_match = _NGV_YEAR_RE.search(cells[0])
        if not year_match:
            continue
        year = int(year_match.group(1))

        # Twelve month columns follow the year label, January first.
        for month, cell in enumerate(cells[1:13], start=1):
            price = _parse_price_value(cell)
            if price is None or not (5 <= price <= 30):
                continue
            obs_date = date(year, month, 1)
            if obs_date <= cutoff:
                continue

            r = _TMPL_TH_NGV.copy()
            r.update(
                {
                    "price_local": round(price, 4),
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date),
                    "observation_date": str(obs_date),
                    "source_url": _NGV_URL,
                }
            )
            r["observation_hash"] = make_hash(r)
            all_rows.append(r)

    if not all_rows:
        print("  [th_eppo_ngv] No new rows")
        return pd.DataFrame()

    print(f"  [th_eppo_ngv] {len(all_rows)} new rows")
    return pd.DataFrame(all_rows)
