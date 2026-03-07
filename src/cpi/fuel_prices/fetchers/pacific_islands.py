"""Pacific Islands fuel price fetchers — PNG, Samoa, Vanuatu, Solomon Islands."""

import re
import time
from datetime import date, timedelta

import pandas as pd
from bs4 import BeautifulSoup

from ..utils import MONTH_MAP_EN, get_session, make_hash, make_template

# ── Papua New Guinea ICCC ──────────────────────────────────────────────────────

_TMPL_PNG = make_template(
    country="Papua New Guinea",
    wb_iso3="PNG",
    source_key="pg_iccc_monthly_irp",
    source_name="Papua New Guinea ICCC Indicative Retail Fuel Prices",
    source_url="https://iccc.gov.pg/category/fuel-prices/",
    currency="PGK",
    unit="L",
    subnational_area="Port Moresby",
    publication_frequency="monthly",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_PNG_PRODUCTS = [
    ("Petrol", "gasoline", "regular", None, r"(?i)petrol|gasoline|mogas"),
    ("Diesel", "diesel", "regular", None, r"(?i)diesel"),
    ("Kerosene", "kerosene", "regular", None, r"(?i)kerosene|kero"),
]


def fetch_png_iccc(cutoff: date) -> pd.DataFrame:
    """Fetch PNG ICCC monthly indicative retail fuel prices."""
    print("  [png_iccc] Fetching PNG ICCC data...")
    print(f"  [png_iccc] Cutoff: {cutoff}")

    session = get_session()
    listing_url = "https://iccc.gov.pg/category/fuel-prices/"

    try:
        resp = session.get(listing_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [png_iccc] Could not fetch listing: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")

    article_links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if (
            "iccc.gov.pg" in href
            and "/fuel-price" in href
            and href not in article_links
        ):
            article_links.append(href)
        elif href.startswith("/") and "/fuel-price" in href:
            full = "https://iccc.gov.pg" + href
            if full not in article_links:
                article_links.append(full)

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "category/fuel-prices/page/" in href:
            try:
                r2 = session.get(href, timeout=20)
                if r2.status_code == 200:
                    s2 = BeautifulSoup(r2.content, "lxml")
                    for a2 in s2.find_all("a", href=True):
                        h2 = a2["href"]
                        if (
                            "iccc.gov.pg" in h2
                            and "/fuel-price" in h2
                            and h2 not in article_links
                        ):
                            article_links.append(h2)
            except Exception:
                pass

    print(f"  [png_iccc] Found {len(article_links)} article links")
    all_rows = []

    for art_url in article_links[:20]:
        try:
            r = session.get(art_url, timeout=20)
            if r.status_code != 200:
                continue
            text = BeautifulSoup(r.content, "lxml").get_text(separator="\n")

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

            if obs_date is None or obs_date <= cutoff:
                continue

            rows_added = 0
            for prod_name, family, qg, ron, prod_pat in _PNG_PRODUCTS:
                m = re.search(
                    rf"{prod_pat}[^\d]{{0,100}}([\d]+\.[\d]{{2,3}})",
                    text,
                    re.IGNORECASE | re.DOTALL,
                )
                if not m:
                    continue
                try:
                    price = float(m.group(1))
                    if not (1.0 <= price <= 20.0):
                        continue
                except ValueError:
                    continue

                month_end = (obs_date.replace(day=28) + timedelta(days=4)).replace(
                    day=1
                ) - timedelta(days=1)
                r_row = _TMPL_PNG.copy()
                r_row.update(
                    {
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "price_local": price,
                        "effective_from": str(obs_date),
                        "effective_to": str(month_end),
                        "observation_date": str(obs_date),
                        "source_url": art_url,
                    }
                )
                r_row["observation_hash"] = make_hash(r_row)
                all_rows.append(r_row)
                rows_added += 1

            if rows_added:
                print(f"  [png_iccc] {obs_date}: {rows_added} products")
        except Exception as e:
            print(f"  [png_iccc] Error {art_url}: {e}")
        time.sleep(0.3)

    if all_rows:
        print(f"  [png_iccc] {len(all_rows)} new rows")
    else:
        print("  [png_iccc] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ── Samoa MOF ─────────────────────────────────────────────────────────────────

_TMPL_WS = make_template(
    country="Samoa",
    wb_iso3="WSM",
    source_key="ws_mof_monthly_fuel_prices",
    source_name="Samoa Ministry of Finance — Monthly Fuel Prices",
    source_url="https://www.mof.gov.ws/press-releases-mof",
    currency="WST",
    unit="L",
    subnational_area="National",
    publication_frequency="monthly",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_WS_PRODUCTS = [
    ("Petrol", "gasoline", "regular", None, r"(?i)\bpetrol\b|\bgasoline\b"),
    ("Diesel", "diesel", "regular", None, r"(?i)\bdiesel\b"),
    ("Kerosene", "kerosene", "regular", None, r"(?i)\bkerosene\b|\bkero\b"),
]


def fetch_samoa_mof(cutoff: date) -> pd.DataFrame:
    """Fetch Samoa Ministry of Finance monthly fuel prices."""
    print("  [ws_mof] Fetching Samoa MOF data...")
    print(f"  [ws_mof] Cutoff: {cutoff}")

    session = get_session()
    listing_url = "https://www.mof.gov.ws/press-releases-mof"

    try:
        resp = session.get(listing_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [ws_mof] Could not fetch listing: {e}")
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
            full = href if href.startswith("http") else "https://www.mof.gov.ws" + href
            if full not in seen:
                seen.add(full)
                article_links.append(full)

    print(f"  [ws_mof] Found {len(article_links)} candidate article links")
    all_rows = []

    for art_url in article_links[:20]:
        try:
            r = session.get(art_url, timeout=20)
            if r.status_code != 200:
                continue
            text = BeautifulSoup(r.content, "lxml").get_text(separator="\n")

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

            if obs_date is None or obs_date <= cutoff:
                continue

            rows_added = 0
            for prod_name, family, qg, ron, prod_pat in _WS_PRODUCTS:
                m = re.search(
                    rf"{prod_pat}[^\d]{{0,150}}(\d+\.\d{{2,3}})",
                    text,
                    re.IGNORECASE | re.DOTALL,
                )
                if not m:
                    continue
                try:
                    price = float(m.group(1))
                    if not (1.0 <= price <= 15.0):
                        continue
                except ValueError:
                    continue

                month_end = (obs_date.replace(day=28) + timedelta(days=4)).replace(
                    day=1
                ) - timedelta(days=1)
                r_row = _TMPL_WS.copy()
                r_row.update(
                    {
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "price_local": price,
                        "effective_from": str(obs_date),
                        "effective_to": str(month_end),
                        "observation_date": str(obs_date),
                        "source_url": art_url,
                    }
                )
                r_row["observation_hash"] = make_hash(r_row)
                all_rows.append(r_row)
                rows_added += 1

            if rows_added:
                print(f"  [ws_mof] {obs_date}: {rows_added} products")
        except Exception as e:
            print(f"  [ws_mof] Error {art_url}: {e}")
        time.sleep(0.3)

    if all_rows:
        print(f"  [ws_mof] {len(all_rows)} new rows")
    else:
        print("  [ws_mof] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


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
