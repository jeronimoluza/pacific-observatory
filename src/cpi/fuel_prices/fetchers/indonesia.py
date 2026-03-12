"""Indonesia OTO.com monthly fuel price fetcher."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_id_oto",
        "country": "Indonesia",
        "source_name": "OTO.com Monthly Fuel Prices",
        "url": "https://www.oto.com/ajax/get-fuel-price-trends",
        "description": "Commercial portal (OTO.com) aggregating Pertamina official prices. Public JSON AJAX endpoint; reflects Pertamina state-enterprise retail rates.",
        "extraction_method": ["REST API"],
        "products": [
            "Pertalite (Gasoline Regular)",
            "Pertamax (Gasoline Premium)",
            "Pertamax Turbo (Gasoline Super Premium)",
            "Dexlite (Diesel Premium)",
            "Pertamina Dex (Diesel Super Premium)",
        ],
        "source_keys": ["id_oto_monthly_prices"],
        "publishes_on": "Monthly (1st of month)",
        "notes": "Public JSON API; no auth required. Fetches rolling 12-month + yearly data for 5 Pertamina fuel IDs. Price range IDR 3,000–30,000/L.",
    },
    {
        "fetcher_fn": "fetch_id_pertamina_pengumuman",
        "country": "Indonesia",
        "source_name": "Pertamina Pengumuman Harga BBM Non-Subsidi",
        "url": "https://www.pertamina.com/pengumuman",
        "description": "Official national oil company (Pertamina). Monthly non-subsidi fuel price announcements with per-wilayah price tables.",
        "extraction_method": ["Playwright", "DOM scraping"],
        "products": [
            "Pertalite",
            "Pertamax",
            "Pertamax Turbo",
            "Pertamax Green 95",
            "Biosolar",
            "Dexlite",
            "Pertamina Dex",
            "Biosolar Non-Subsidi",
            "Pertamax di Pertashop",
        ],
        "source_keys": ["id_pertamina_pengumuman_non_subsidi"],
        "publishes_on": "Monthly (TMT 1st of month)",
        "notes": "Requires Playwright Python package + browser binaries. Scrapes tables from announcement pages such as 'daftar-harga-bahan-bakar-khusus-non-subsidi-tmt-1-<bulan>-<tahun>'.",
    },
]

import re
from datetime import date, datetime, timedelta

import pandas as pd

from ..utils import get_session, make_hash, make_template

_TMPL_ID = make_template(
    country="Indonesia",
    wb_iso3="IDN",
    source_key="id_oto_monthly_prices",
    source_name="OTO.com Indonesia Fuel Prices",
    source_url="https://www.oto.com/en/harga-bbm",
    currency="IDR",
    unit="L",
    subnational_area="National",
    publication_frequency="monthly",
    observation_method="survey",
)

_ID_OTO_PRODUCTS = [
    (1, "Pertalite", "gasoline", "regular", None),
    (2, "Pertamax Turbo", "gasoline", "super_premium", None),
    (3, "Pertamax", "gasoline", "premium", None),
    (4, "Dexlite", "diesel", "premium", None),
    (5, "Pertamina Dex", "diesel", "super_premium", None),
]

_ID_OTO_BASE_URL = "https://www.oto.com/ajax/get-fuel-price-trends"

_ID_PERTAMINA_PENGUMUMAN_URL = "https://www.pertamina.com/pengumuman"
_ID_PERTAMINA_NEWS_PREFIX = "https://www.pertamina.com/news/"
_ID_PERTAMINA_SLUG_RE = re.compile(
    r"daftar-harga-bahan-bakar-khusus-non-subsidi-tmt-(\d{1,2})-([a-z]+)-(\d{4})",
    re.IGNORECASE,
)
_ID_PERTAMINA_HEADERS = {
    "WILAYAH": None,
    "PERTALITE": ("Pertalite", "gasoline", "regular", None),
    "PERTAMAX": ("Pertamax", "gasoline", "premium", None),
    "PERTAMAX TURBO": ("Pertamax Turbo", "gasoline", "super_premium", None),
    "PERTAMAX GREEN 95": ("Pertamax Green 95", "gasoline", "premium", 95),
    "BIOSOLAR": ("Biosolar", "diesel", "regular", None),
    "DEXLITE": ("Dexlite", "diesel", "premium", None),
    "PERTAMINA DEX": ("Pertamina Dex", "diesel", "super_premium", None),
    "BIOSOLAR NON-SUBSIDI": ("Biosolar Non-Subsidi", "diesel", "regular", None),
    "PERTAMAX DI PERTASHOP": ("Pertamax di Pertashop", "gasoline", "premium", None),
}

_ID_MONTHS = {
    "januari": 1,
    "februari": 2,
    "maret": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "agustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "desember": 12,
}


def _parse_id_slug_date(slug: str) -> date | None:
    match = _ID_PERTAMINA_SLUG_RE.search(slug)
    if not match:
        return None
    day = int(match.group(1))
    mon = _ID_MONTHS.get(match.group(2).lower())
    year = int(match.group(3))
    if not mon:
        return None
    try:
        return date(year, mon, day)
    except ValueError:
        return None


def _parse_idr_price(raw: str) -> float | None:
    if not raw:
        return None
    raw = raw.replace("Rp", "").replace("rp", "")
    raw = raw.replace(".", "").replace(",", "")
    raw = re.sub(r"[^0-9]", "", raw)
    if not raw:
        return None
    try:
        price = float(raw)
    except ValueError:
        return None
    if not (3_000 <= price <= 30_000):
        return None
    return price


def _extract_pertamina_table(page) -> tuple[list[str], list[list[str]]]:
    table = page.locator("table").first
    if table.count() == 0:
        return [], []

    header_cells = table.locator("thead th").all()
    if not header_cells:
        header_cells = table.locator("tr").first.locator("th,td").all()
    headers = [c.inner_text().strip() for c in header_cells if c.inner_text().strip()]

    body_rows = table.locator("tbody tr").all()
    if not body_rows:
        body_rows = table.locator("tr").all()[1:]

    rows = []
    for row in body_rows:
        cells = [c.inner_text().strip() for c in row.locator("th,td").all()]
        if cells:
            rows.append(cells)

    return headers, rows


def fetch_id_oto(cutoff: date) -> pd.DataFrame:
    """Fetch Indonesia fuel prices from OTO.com public JSON API (full refresh)."""
    print("  [id_oto] Fetching Indonesia OTO.com data (full refresh)...")

    session = get_session()
    all_rows = []

    for fuel_id, prod_name, family, qg, ron in _ID_OTO_PRODUCTS:
        rows_for_product: dict[date, tuple[float, date]] = {}
        monthly_years: set[int] = set()

        # Monthly data (rolling 12-month window)
        try:
            resp = session.get(
                _ID_OTO_BASE_URL,
                params={"fuelId": fuel_id, "input": "month", "categorySlug": "mobil"},
                timeout=15,
            )
        except Exception as e:
            print(f"  [id_oto] Request error (fuelId={fuel_id}, month): {e}")
            resp = None

        if resp is not None and resp.status_code == 200:
            try:
                items = resp.json()
            except Exception:
                items = []
            for item in items:
                text, value = item.get("text", ""), item.get("value", 0)
                try:
                    obs_date = datetime.strptime(text, "%b %y").date()
                    next_m = obs_date.replace(day=28) + timedelta(days=4)
                    eff_to = next_m - timedelta(days=next_m.day)
                except Exception:
                    continue
                if not (3000 <= value <= 30000):
                    continue
                rows_for_product[obs_date] = (float(value), eff_to)
                monthly_years.add(obs_date.year)

        # Yearly data — skip any year already covered by monthly entries
        try:
            resp = session.get(
                _ID_OTO_BASE_URL,
                params={"fuelId": fuel_id, "input": "year", "categorySlug": "mobil"},
                timeout=15,
            )
        except Exception as e:
            print(f"  [id_oto] Request error (fuelId={fuel_id}, year): {e}")
            resp = None

        if resp is not None and resp.status_code == 200:
            try:
                items = resp.json()
            except Exception:
                items = []
            for item in items:
                text, value = item.get("text", ""), item.get("value", 0)
                try:
                    year = int(text)
                    obs_date = date(year, 1, 1)
                    eff_to = date(year, 12, 31)
                except Exception:
                    continue
                if year in monthly_years:
                    continue
                if not (3000 <= value <= 30000):
                    continue
                rows_for_product[obs_date] = (float(value), eff_to)

        for obs_date, (price, eff_to) in sorted(rows_for_product.items()):
            if obs_date <= cutoff:
                continue
            r = _TMPL_ID.copy()
            r.update(
                {
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "price_local": price,
                    "effective_from": str(obs_date),
                    "effective_to": str(eff_to),
                    "observation_date": str(obs_date),
                    "source_url": _ID_OTO_BASE_URL,
                }
            )
            r["observation_hash"] = make_hash(r)
            all_rows.append(r)

    print(f"  [id_oto] {len(all_rows)} rows fetched (cutoff {cutoff})")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


def fetch_id_pertamina_pengumuman(cutoff: date) -> pd.DataFrame:
    """Fetch Indonesia fuel prices from Pertamina Pengumuman announcement tables."""
    print("  [id_pertamina] Fetching Pertamina Pengumuman tables (Playwright)...")
    print(f"  [id_pertamina] Cutoff: {cutoff}")

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(f"  [id_pertamina] Playwright not available: {e}")
        return pd.DataFrame()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(
                _ID_PERTAMINA_PENGUMUMAN_URL, wait_until="networkidle", timeout=60_000
            )
            page.wait_for_timeout(6_000)
        except Exception as e:
            print(f"  [id_pertamina] Pengumuman load error: {e}")
            browser.close()
            return pd.DataFrame()

        links = page.locator("a[href]").all()
        candidates = []
        for a in links:
            href = a.get_attribute("href") or ""
            if "daftar-harga-bahan-bakar-khusus-non-subsidi" not in href:
                continue
            slug = href.split("/")[-1]
            eff_date = _parse_id_slug_date(slug)
            if not eff_date:
                continue
            url = (
                href
                if href.startswith("http")
                else f"{_ID_PERTAMINA_NEWS_PREFIX}{slug}"
            )
            candidates.append((eff_date, url))

        if not candidates:
            print("  [id_pertamina] No announcement links found")
            browser.close()
            return pd.DataFrame()

        eff_date, url = max(candidates, key=lambda x: x[0])
        if eff_date <= cutoff:
            print(
                f"  [id_pertamina] Date {eff_date} not newer than cutoff {cutoff}, skipping"
            )
            browser.close()
            return pd.DataFrame()

        try:
            page.goto(url, wait_until="networkidle", timeout=60_000)
            page.wait_for_timeout(8_000)
        except Exception as e:
            print(f"  [id_pertamina] Announcement load error: {e}")
            browser.close()
            return pd.DataFrame()

        headers, rows = _extract_pertamina_table(page)
        browser.close()

    if not headers or not rows:
        print("  [id_pertamina] No table rows found")
        return pd.DataFrame()

    header_map = []
    for h in headers:
        key = h.upper().strip()
        header_map.append(_ID_PERTAMINA_HEADERS.get(key))

    tmpl = make_template(
        country="Indonesia",
        wb_iso3="IDN",
        source_key="id_pertamina_pengumuman_non_subsidi",
        source_name="Pertamina Pengumuman Non-Subsidi",
        source_url=url,
        currency="IDR",
        unit="L",
        publication_frequency="monthly",
        observation_method="reported",
        tax_status="tax_inclusive",
    )

    all_rows = []
    for cells in rows:
        if not cells:
            continue
        wilayah = cells[0].strip() if cells else None
        if not wilayah:
            continue
        for idx, cell in enumerate(cells[1:], start=1):
            if idx >= len(header_map):
                continue
            meta = header_map[idx]
            if not meta:
                continue
            price = _parse_idr_price(cell)
            if price is None:
                continue
            prod_name, family, qg, ron = meta
            r = tmpl.copy()
            r.update(
                {
                    "subnational_area": wilayah,
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "price_local": price,
                    "effective_from": str(eff_date),
                    "effective_to": str(eff_date),
                    "observation_date": str(eff_date),
                }
            )
            r["observation_hash"] = make_hash(r)
            all_rows.append(r)

    if all_rows:
        print(f"  [id_pertamina] {len(all_rows)} rows fetched for {eff_date}")
    else:
        print("  [id_pertamina] No price rows parsed")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
