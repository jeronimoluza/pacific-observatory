"""Cambodia PTT monthly retail pump prices (ptt.com.kh).

Ported unchanged from legacy pacific-observatory
``src/cpi/fuel_prices/fetchers/cambodia.py::fetch_kh_ptt`` (dev 2d60a353).
"""

import re
import time
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from fuel.fetchers._shared.eap.legacy import MONTH_MAP_EN, get_session, make_hash, make_template

# ── PTT Cambodia monthly prices (canonical) ──────────────────────────────────

_TMPL_KH_PTT = make_template(
    country="Cambodia",
    wb_iso3="KHM",
    source_key="kh_ptt_monthly_prices",
    source_name="PTT Cambodia",
    source_url="https://www.ptt.com.kh/products-and-services-oil-price",
    currency="KHR",
    unit="L",
    publication_frequency="monthly",
)

_KH_PRODUCTS = [
    ("super", "Super", "gasoline", "premium", None),
    ("regular", "Regular", "gasoline", "regular", None),
    ("diesel", "Diesel", "diesel", "regular", None),
]


def fetch_kh_ptt(cutoff: date) -> pd.DataFrame:
    """Fetch Cambodia PTT monthly oil prices from ptt.com.kh."""
    print("  [kh_ptt] Fetching Cambodia PTT data...")
    print(f"  [kh_ptt] Cutoff: {cutoff}")

    session = get_session()
    today = date.today()
    all_rows = []

    for year in range(max(cutoff.year, 2019), today.year + 1):
        url = f"https://www.ptt.com.kh/products-and-services-oil-price?months=0&year={year}"
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code != 200:
                print(f"  [kh_ptt] HTTP {resp.status_code} for year {year}")
                continue
        except Exception as e:
            print(f"  [kh_ptt] Fetch error year {year}: {e}")
            continue

        soup = BeautifulSoup(resp.content, "lxml")
        for table in soup.find_all("table"):
            rows_html = table.find_all("tr")
            if len(rows_html) < 3:
                continue

            header_cells = rows_html[0].find_all(["th", "td"])
            headers = [c.get_text(strip=True).lower() for c in header_cells]

            date_col = next(
                (i for i, h in enumerate(headers) if "date" in h or "month" in h),
                0 if headers else None,
            )
            if date_col is None:
                continue

            prod_cols: dict[int, tuple] = {}
            for ci, h in enumerate(headers):
                if ci == date_col:
                    continue
                for key, prod_name, family, qg, ron in _KH_PRODUCTS:
                    if key in h:
                        prod_cols[ci] = (prod_name, family, qg, ron)
                        break

            if not prod_cols:
                non_date = [i for i in range(len(headers)) if i != date_col]
                for ci, (key, prod_name, family, qg, ron) in zip(
                    non_date, _KH_PRODUCTS
                ):
                    prod_cols[ci] = (prod_name, family, qg, ron)

            for row in rows_html[1:]:
                cells = row.find_all(["th", "td"])
                if len(cells) <= date_col:
                    continue
                texts = [c.get_text(strip=True) for c in cells]
                date_str = texts[date_col] if date_col < len(texts) else ""

                obs_date = None
                for pat, parse_fn in [
                    (
                        r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})",
                        lambda m: date(
                            int(m.group(1)), int(m.group(2)), int(m.group(3))
                        ),
                    ),
                    (
                        r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
                        lambda m: date(
                            int(m.group(3)), int(m.group(2)), int(m.group(1))
                        ),
                    ),
                ]:
                    m = re.search(pat, date_str)
                    if m:
                        try:
                            obs_date = parse_fn(m)
                            break
                        except ValueError:
                            pass

                if obs_date is None:
                    m = re.match(r"([A-Za-z]{3})-(\d{1,2})-(\d{4})", date_str)
                    if m:
                        try:
                            obs_date = date(
                                int(m.group(3)),
                                MONTH_MAP_EN[m.group(1).lower()],
                                int(m.group(2)),
                            )
                        except (ValueError, KeyError):
                            pass

                if obs_date is None:
                    for mo_name, mo_num in MONTH_MAP_EN.items():
                        if mo_name in date_str.lower():
                            y_m = re.search(r"\b(\d{4})\b", date_str)
                            if y_m:
                                try:
                                    obs_date = date(int(y_m.group(1)), mo_num, 1)
                                    break
                                except ValueError:
                                    pass

                if obs_date is None or obs_date <= cutoff:
                    continue

                for ci, (prod_name, family, qg, ron) in prod_cols.items():
                    if ci >= len(texts):
                        continue
                    try:
                        price = float(re.sub(r"[^0-9.]", "", texts[ci]))
                        if not (2000 <= price <= 20000):
                            continue
                    except (ValueError, TypeError):
                        continue

                    r = _TMPL_KH_PTT.copy()
                    r.update(
                        {
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

        time.sleep(0.5)

    if all_rows:
        print(f"  [kh_ptt] {len(all_rows)} new rows")
    else:
        print("  [kh_ptt] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


__all__ = ["fetch_kh_ptt"]
