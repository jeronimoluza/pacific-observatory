"""Solomon Islands petroleum and LPG price-control notices (one fetcher, two source_keys).

Split out unchanged from legacy pacific-observatory
``src/cpi/fuel_prices/fetchers/pacific_islands.py::fetch_solomon_islands`` (dev 2d60a353).
"""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_solomon_islands",
        "country": "Solomon Islands",
        "source_name": "Government Price Control Gazette",
        "url": "https://solomons.gov.sb/",
        "description": "Official government (Solomon Islands). Legally regulated price control gazette notices for petroleum and LPG as press/media releases.",
        "extraction_method": ["Web scraping"],
        "products": ["Gasoline (Petrol PMS)", "Diesel ADO", "Propane LPG"],
        "source_keys": ["sb_price_control_petroleum_2025", "sb_price_control_lpg_2025"],
        "publishes_on": "Monthly (irregular amendment)",
        "notes": "Scans government website for fuel/price keywords. Processes up to 30 candidate links. Price range SBD 5–30/L (petroleum), SBD 10–200/kg (LPG).",
    },
]

import re
import time
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from fuel.fetchers._shared.eap.legacy import MONTH_MAP_EN, get_session, make_hash, make_template

# ── Solomon Islands ───────────────────────────────────────────────────────────

_TMPL_SB_PETROL = make_template(
    country="Solomon Islands",
    wb_iso3="SLB",
    source_key="sb_price_control_petroleum_2025",
    source_name="Solomon Islands Petroleum Price Control",
    source_url="https://solomons.gov.sb/",
    currency="SBD",
    unit="L",
    subnational_area="National",
    publication_frequency="monthly",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_TMPL_SB_LPG = make_template(
    country="Solomon Islands",
    wb_iso3="SLB",
    source_key="sb_price_control_lpg_2025",
    source_name="Solomon Islands LPG Price Control",
    source_url="https://solomons.gov.sb/",
    currency="SBD",
    unit="kg",
    subnational_area="National",
    publication_frequency="monthly",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_SB_SOURCES = {
    "sb_price_control_petroleum_2025": {
        "tmpl": _TMPL_SB_PETROL,
        "products": [
            ("Diesel (ADO)", "diesel", None, None, r"(?i)diesel|ado|automotive"),
            (
                "Petrol (PMS)",
                "gasoline",
                "regular",
                None,
                r"(?i)petrol|pms|motor spirit",
            ),
        ],
        "price_range": (5, 30),
    },
    "sb_price_control_lpg_2025": {
        "tmpl": _TMPL_SB_LPG,
        "products": [
            ("Propane LPG", "lpg", "regular", None, r"(?i)lpg|propane"),
        ],
        "price_range": (10, 200),
    },
}

_SB_SCAN_URLS = [
    "https://solomons.gov.sb/",
    "https://solomons.gov.sb/category/media-releases/",
    "https://solomons.gov.sb/category/press-releases/",
    "https://solomons.gov.sb/search/?q=fuel+price",
    "https://solomons.gov.sb/search/?q=price+control+petroleum",
    "https://solomons.gov.sb/search/?q=lpg+price",
]


def fetch_solomon_islands(cutoff: date) -> pd.DataFrame:
    """Fetch Solomon Islands petroleum and LPG price-control gazette notices."""
    print("  [sb] Fetching Solomon Islands data...")
    print(f"  [sb] Cutoff: {cutoff}")

    session = get_session()
    article_links: set[str] = set()

    for scan_url in _SB_SCAN_URLS:
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
                    for kw in ["fuel", "petrol", "diesel", "lpg", "price control"]
                ):
                    full = (
                        href
                        if href.startswith("http")
                        else "https://solomons.gov.sb/" + href.lstrip("/")
                    )
                    article_links.add(full)
        except Exception:
            pass
        time.sleep(0.3)

    print(f"  [sb] Found {len(article_links)} candidate links")
    all_rows: list[dict] = []

    for art_url in list(article_links)[:30]:
        try:
            r = session.get(art_url, timeout=20)
            if r.status_code != 200:
                continue
            text = BeautifulSoup(r.content, "lxml").get_text(separator="\n")

            if not any(
                kw in text.lower() for kw in ["fuel", "petrol", "diesel", "lpg"]
            ):
                continue

            is_lpg = bool(re.search(r"(?i)\blpg\b|\bpropane\b", text))
            is_petrol = bool(
                re.search(r"(?i)\bpetrol\b|\bdiesel\b|\bpms\b|\bado\b", text)
            )

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

            for source_key, spec in _SB_SOURCES.items():
                if source_key == "sb_price_control_lpg_2025" and not is_lpg:
                    continue
                if source_key == "sb_price_control_petroleum_2025" and not is_petrol:
                    continue

                tmpl = spec["tmpl"]
                min_p, max_p = spec["price_range"]
                for prod_name, family, qg, ron, prod_pat in spec["products"]:
                    m = re.search(
                        rf"{prod_pat}[^\d]{{0,150}}(\d+(?:\.\d{{1,2}})?)",
                        text,
                        re.IGNORECASE | re.DOTALL,
                    )
                    if not m:
                        continue
                    try:
                        price = float(m.group(1))
                        if not (min_p <= price <= max_p):
                            continue
                    except ValueError:
                        continue

                    r_row = tmpl.copy()
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

        except Exception as e:
            print(f"  [sb] Error {art_url}: {e}")
        time.sleep(0.2)

    for source_key in _SB_SOURCES:
        count = sum(1 for r in all_rows if r.get("source_key") == source_key)
        print(f"  [sb] {source_key}: {count} new rows")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
