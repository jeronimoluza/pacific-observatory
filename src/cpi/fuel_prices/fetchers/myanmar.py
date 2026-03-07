"""Myanmar GNLM weekly fuel reference price fetcher."""

import re
import time
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from ..utils import MONTH_MAP_EN, get_session, make_hash, make_template

_TMPL_MM = make_template(
    country="Myanmar",
    wb_iso3="MMR",
    source_key="mm_gnlm_fuel_reference_prices",
    source_name="Myanmar Global New Light — Fuel Reference Prices",
    source_url="https://www.gnlm.com.mm/",
    currency="MMK",
    unit="L",
    subnational_area="National",
    publication_frequency="weekly",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_PRODUCTS = [
    (
        "Octane 92",
        "gasoline",
        "regular",
        92,
        r"(?i)octane.{0,5}92|ron.{0,5}92|92.{0,5}octane",
    ),
    (
        "Octane 95",
        "gasoline",
        "premium",
        95,
        r"(?i)octane.{0,5}95|ron.{0,5}95|95.{0,5}octane",
    ),
    ("Diesel", "diesel", "regular", None, r"(?i)\bdiesel\b"),
    (
        "Premium Diesel",
        "diesel",
        "premium",
        None,
        r"(?i)premium diesel|high.quality diesel",
    ),
]

_SCAN_URLS = [
    "https://www.gnlm.com.mm/?s=fuel+price",
    "https://www.gnlm.com.mm/?s=petroleum+price",
    "https://www.gnlm.com.mm/?s=petrol+price",
    "https://www.gnlm.com.mm/",
]


def fetch_myanmar_gnlm(cutoff: date) -> pd.DataFrame:
    """Fetch Myanmar GNLM weekly fuel reference prices."""
    print("  [mm_gnlm] Fetching Myanmar GNLM data...")
    print(f"  [mm_gnlm] Cutoff: {cutoff}")

    session = get_session()
    today = date.today()
    all_rows = []

    article_links: set[str] = set()
    for scan_url in _SCAN_URLS:
        try:
            r = session.get(scan_url, timeout=20)
            if r.status_code != 200:
                continue
            s = BeautifulSoup(r.content, "lxml")
            for a in s.find_all("a", href=True):
                href = a["href"]
                link_text = a.get_text(strip=True).lower()
                if any(
                    kw in link_text or kw in href.lower()
                    for kw in [
                        "fuel",
                        "petrol",
                        "diesel",
                        "price",
                        "petroleum",
                        "octane",
                    ]
                ):
                    if "gnlm.com.mm" in href:
                        article_links.add(href)
        except Exception as e:
            print(f"  [mm_gnlm] Scan error {scan_url}: {e}")
        time.sleep(0.3)

    print(f"  [mm_gnlm] Found {len(article_links)} candidate links")

    for art_url in list(article_links)[:30]:
        try:
            r = session.get(art_url, timeout=20)
            if r.status_code != 200:
                continue
            art_soup = BeautifulSoup(r.content, "lxml")
            text = art_soup.get_text(separator="\n")

            if not any(
                kw in text.lower() for kw in ["fuel", "octane", "diesel", "petroleum"]
            ):
                continue

            obs_date = None
            iso_m = re.search(r"(20\d{2})[/\-](\d{2})[/\-](\d{2})", text)
            if iso_m:
                try:
                    obs_date = date(
                        int(iso_m.group(1)), int(iso_m.group(2)), int(iso_m.group(3))
                    )
                except ValueError:
                    pass
            if obs_date is None:
                for month_name, month_num in MONTH_MAP_EN.items():
                    if len(month_name) < 4:
                        continue  # skip 3-letter abbrevs to avoid false positives
                    if month_name in text.lower():
                        year_m = re.search(r"\b(20\d{2})\b", text)
                        if year_m:
                            try:
                                obs_date = date(int(year_m.group(1)), month_num, 1)
                                break
                            except ValueError:
                                pass

            if obs_date is None or obs_date <= cutoff or obs_date > today:
                continue

            rows_added = 0
            for prod_name, family, qg, ron, prod_pat in _PRODUCTS:
                m = re.search(
                    rf"{prod_pat}[^\d]{{0,150}}(\d{{3,5}}(?:\.\d{{1,2}})?)",
                    text,
                    re.IGNORECASE | re.DOTALL,
                )
                if not m:
                    continue
                try:
                    price = float(m.group(1))
                    if not (500 <= price <= 5000):
                        continue
                except ValueError:
                    continue

                r_row = _TMPL_MM.copy()
                r_row.update(
                    {
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "price_local": price,
                        "effective_from": str(obs_date),
                        "effective_to": str(obs_date),
                        "observation_date": str(obs_date),
                        "source_url": art_url,
                    }
                )
                r_row["observation_hash"] = make_hash(r_row)
                all_rows.append(r_row)
                rows_added += 1

            if rows_added:
                print(f"  [mm_gnlm] {obs_date}: {rows_added} products from {art_url}")

        except Exception as e:
            print(f"  [mm_gnlm] Error {art_url}: {e}")
        time.sleep(0.3)

    if all_rows:
        print(f"  [mm_gnlm] {len(all_rows)} new rows")
    else:
        print("  [mm_gnlm] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
