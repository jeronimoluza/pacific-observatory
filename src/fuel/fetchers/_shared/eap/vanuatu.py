"""Vanuatu Department of Energy retail fuel prices (disabled in legacy since 0cfd749b).

Split out unchanged from legacy pacific-observatory
``src/cpi/fuel_prices/fetchers/pacific_islands.py::fetch_vanuatu_doe`` (dev 2d60a353).
"""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_vanuatu_doe",
        "country": "Vanuatu",
        "source_name": "Department of Energy Retail Fuel Prices",
        "url": "https://doe.gov.vu/index.php/news-events/news",
        "description": "Official government (Vanuatu Dept. of Energy). Monthly retail fuel price announcements as news articles. Prices in unstructured text.",
        "extraction_method": ["Web scraping"],
        "products": ["Gasoline Unleaded 95RON (Premium)", "Diesel Low Sulphur 10PPM"],
        "source_keys": ["vu_doe_retail_petrol_diesel_2025"],
        "publishes_on": "Monthly (irregular notice)",
        "notes": "WARNING: SSL verification disabled (verify=False). Processes up to 25 candidate links. Price range VUV 100–500/L.",
    },
]

import re
import time
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from fuel.fetchers._shared.eap.legacy import MONTH_MAP_EN, get_session, make_hash, make_template

# ── Vanuatu DOE ───────────────────────────────────────────────────────────────

_TMPL_VU = make_template(
    country="Vanuatu",
    wb_iso3="VUT",
    source_key="vu_doe_retail_petrol_diesel_2025",
    source_name="Vanuatu Department of Energy — Retail Fuel Prices",
    source_url="https://doe.gov.vu/index.php/news-events/news",
    currency="VUV",
    unit="L",
    subnational_area="National",
    publication_frequency="monthly",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_VU_PRODUCTS = [
    (
        "Unleaded Petrol 95RON",
        "gasoline",
        "premium",
        95,
        r"(?i)(unleaded|petrol|gasoline|essence)",
    ),
    ("Low Sulphur Diesel 10PPM", "diesel", "regular", None, r"(?i)diesel|gasoil"),
]


def fetch_vanuatu_doe(cutoff: date) -> pd.DataFrame:
    """Fetch Vanuatu Department of Energy retail fuel prices."""
    # Disabled 2026-10-16: the news listing yields unrelated articles and the
    # date is guessed from the first month name / year in the text (e.g. 2030
    # from "Vision 2030"), so even with the product regexes fixed it emits
    # wrong rows. Last valid data: 2025-12-31. Needs a rewrite against DOE's
    # actual price notices before re-enabling.
    print("  [vu_doe] Disabled: parser unreliable (see fetch_vanuatu_doe)")
    return pd.DataFrame()
    print("  [vu_doe] Fetching Vanuatu DOE data...")
    print(f"  [vu_doe] Cutoff: {cutoff}")

    session = get_session()
    listing_url = "https://doe.gov.vu/index.php/news-events/news"

    try:
        resp = session.get(listing_url, timeout=30, verify=False)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [vu_doe] Could not fetch listing: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")
    article_links: list[str] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        link_text = a.get_text(strip=True).lower()
        if any(
            kw in link_text or kw in href.lower()
            for kw in ["fuel", "petrol", "diesel", "price"]
        ):
            full = href if href.startswith("http") else "https://doe.gov.vu" + href
            if full not in seen:
                seen.add(full)
                article_links.append(full)

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "doe.gov.vu" in href and "/news" in href and href not in seen:
            seen.add(href)
            article_links.append(href)
        elif href.startswith("/") and "/news" in href:
            full = "https://doe.gov.vu" + href
            if full not in seen:
                seen.add(full)
                article_links.append(full)

    print(f"  [vu_doe] Found {len(article_links)} candidate links")
    all_rows = []

    for art_url in article_links[:25]:
        try:
            r = session.get(art_url, timeout=20, verify=False)
            if r.status_code != 200:
                continue
            text = BeautifulSoup(r.content, "lxml").get_text(separator="\n")

            if not any(kw in text.lower() for kw in ["fuel", "petrol", "diesel"]):
                continue

            obs_date = None
            for month_name, month_num in MONTH_MAP_EN.items():
                if len(month_name) < 4:
                    continue
                if month_name in text.lower():
                    year_m = re.search(r"\b(20\d{2})\b", text)
                    if year_m:
                        try:
                            obs_date = date(int(year_m.group(1)), month_num, 1)
                            break
                        except ValueError:
                            pass
            if obs_date is None:
                iso_m = re.search(r"(20\d{2})[/\-](\d{2})[/\-](\d{2})", text)
                if iso_m:
                    try:
                        obs_date = date(
                            int(iso_m.group(1)),
                            int(iso_m.group(2)),
                            int(iso_m.group(3)),
                        )
                    except ValueError:
                        pass

            if obs_date is None or obs_date <= cutoff:
                continue

            rows_added = 0
            for prod_name, family, qg, ron, prod_pat in _VU_PRODUCTS:
                m = re.search(
                    rf"{prod_pat}[^\d]{{0,150}}(\d{{3,4}}(?:\.\d{{1,2}})?)",
                    text,
                    re.IGNORECASE | re.DOTALL,
                )
                if not m:
                    continue
                try:
                    price = float(m.group(1))
                    if not (100 <= price <= 500):
                        continue
                except ValueError:
                    continue

                r_row = _TMPL_VU.copy()
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
                print(f"  [vu_doe] {obs_date}: {rows_added} products")
        except Exception as e:
            print(f"  [vu_doe] Error {art_url}: {e}")
        time.sleep(0.3)

    if all_rows:
        print(f"  [vu_doe] {len(all_rows)} new rows")
    else:
        print("  [vu_doe] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
