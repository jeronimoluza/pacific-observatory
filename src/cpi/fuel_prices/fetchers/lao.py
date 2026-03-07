"""Lao State Fuel Company provincial price fetcher."""

import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from ..utils import get_session, make_hash, make_template

_TMPL_LAO = make_template(
    country="Lao PDR",
    wb_iso3="LAO",
    source_key="lao_state_fuel_oil_prices",
    source_name="Lao State Fuel Company — Provincial Retail Prices",
    source_url="https://www.laostatefuel.com/en/gas-price.html",
    currency="LAK",
    unit="L",
    consumer_segment="retail",
    publication_frequency="monthly",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_PRODUCT_COLS = {
    "gasoline 95": ("Gasoline 95", "gasoline", "premium", 95),
    "95": ("Gasoline 95", "gasoline", "premium", 95),
    "regular": ("Regular Gasoline", "gasoline", "regular", None),
    "diesel": ("Diesel", "diesel", "regular", None),
}


def fetch_lao(cutoff: date) -> pd.DataFrame:
    """Fetch Lao State Fuel provincial prices from laostatefuel.com."""
    print("  [lao] Fetching Lao PDR data...")
    print(f"  [lao] Cutoff: {cutoff}")

    session = get_session()
    url = "https://www.laostatefuel.com/en/gas-price.html"

    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [lao] Could not fetch page: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")
    all_rows = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue

        header_cells = rows[0].find_all(["th", "td"])
        headers = [c.get_text(strip=True).lower() for c in header_cells]

        if "province" not in " ".join(headers) or "date" not in " ".join(headers):
            continue

        try:
            prov_col = next(i for i, h in enumerate(headers) if "province" in h)
            date_col = next(
                i for i, h in enumerate(headers) if "date" in h and "province" not in h
            )
        except StopIteration:
            continue

        price_cols = {}
        for col_idx, h in enumerate(headers):
            for key, meta in _PRODUCT_COLS.items():
                if key in h and col_idx not in (prov_col, date_col):
                    price_cols[col_idx] = meta
                    break

        if not price_cols:
            continue

        for row in rows[1:]:
            cells = row.find_all(["th", "td"])
            if len(cells) <= max(date_col, prov_col):
                continue
            cell_texts = [c.get_text(strip=True) for c in cells]

            province = cell_texts[prov_col] if prov_col < len(cell_texts) else None
            date_str = cell_texts[date_col] if date_col < len(cell_texts) else None

            if not province or not date_str:
                continue

            m = re.match(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", date_str)
            if not m:
                continue
            try:
                obs_date = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                continue

            if obs_date <= cutoff:
                continue

            for col_idx, (prod_name, family, qg, ron) in price_cols.items():
                if col_idx >= len(cell_texts):
                    continue
                price_str = cell_texts[col_idx]
                try:
                    price = float(re.sub(r"[^0-9.]", "", price_str))
                    if price < 5000 or price > 100000:
                        continue
                except (ValueError, TypeError):
                    continue

                r = _TMPL_LAO.copy()
                r.update(
                    {
                        "subnational_area": province,
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "price_local": price,
                        "effective_from": str(obs_date),
                        "effective_to": str(obs_date),
                        "observation_date": str(obs_date),
                        "source_url": url,
                    }
                )
                r["observation_hash"] = make_hash(r)
                all_rows.append(r)

    if all_rows:
        max_d = max(r["observation_date"] for r in all_rows)
        print(f"  [lao] Collected {len(all_rows)} new rows (max date: {max_d})")
    else:
        all_dates = []
        for table in soup.find_all("table"):
            for table_row in table.find_all("tr")[1:]:
                for cell in table_row.find_all(["th", "td"]):
                    m = re.match(
                        r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})",
                        cell.get_text(strip=True),
                    )
                    if m:
                        try:
                            all_dates.append(
                                date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                            )
                        except ValueError:
                            pass
        latest = max(all_dates) if all_dates else None
        print(f"  [lao] No new rows (site date: {latest}, cutoff: {cutoff})")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
