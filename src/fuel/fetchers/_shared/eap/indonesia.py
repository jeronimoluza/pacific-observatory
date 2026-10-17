"""Indonesia fuel price fetchers: OTO.com monthly + Pertamina announcements."""

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
from calendar import monthrange
from datetime import date, datetime, timedelta

import pandas as pd

from fuel.fetchers._shared.eap.legacy import get_session, make_hash, make_template

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
    "PERTAMAX RACING": ("Pertamax Racing", "gasoline", "super_premium", None),
    "BIOSOLAR": ("Biosolar", "diesel", "regular", None),
    "DEXLITE": ("Dexlite", "diesel", "premium", None),
    "PERTAMINA DEX": ("Pertamina Dex", "diesel", "super_premium", None),
    "BIOSOLAR NON-SUBSIDI": ("Biosolar Non-Subsidi", "diesel", "regular", None),
    "SOLAR NON-SUBSIDI": ("Biosolar Non-Subsidi", "diesel", "regular", None),
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

_ID_MONTHS_REV = {v: k for k, v in _ID_MONTHS.items()}
_ID_PERTAMINA_EARLIEST_KNOWN = date(2023, 8, 1)
_ID_PERTAMINA_SPECIAL_URLS = {
    date(2025, 12, 1): [
        (
            "https://www.pertamina.com/news/"
            "daftar-harga-bahan-bakar-khusus-non-subsidi-tmt-1-desember-2025-all-zone"
        ),
        (
            "https://www.pertamina.com/news/"
            "daftar-harga-bahan-bakar-khusus-non-subsidi-tmt-1-desember-2025-zona-1"
        ),
        (
            "https://www.pertamina.com/news/"
            "daftar-harga-bahan-bakar-khusus-non-subsidi-tmt-1-desember-2025-zona-ii"
        ),
    ]
}


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _next_month(d: date) -> date:
    year = d.year + (1 if d.month == 12 else 0)
    month = 1 if d.month == 12 else d.month + 1
    return date(year, month, 1)


def _previous_month(d: date) -> date:
    year = d.year - (1 if d.month == 1 else 0)
    month = 12 if d.month == 1 else d.month - 1
    return date(year, month, 1)


def _pertamina_default_url(eff_date: date) -> str:
    month_name = _ID_MONTHS_REV[eff_date.month]
    return (
        f"{_ID_PERTAMINA_NEWS_PREFIX}"
        f"daftar-harga-bahan-bakar-khusus-non-subsidi-tmt-{eff_date.day}-"
        f"{month_name}-{eff_date.year}"
    )


def _pertamina_url_priority(url: str) -> tuple[int, str]:
    url_l = url.lower()
    if "all-zone" in url_l or "semua-zona" in url_l:
        return (0, url)
    if "zona" not in url_l:
        return (1, url)
    if "zona-i" in url_l or "zona-1" in url_l:
        return (2, url)
    if "zona-ii" in url_l or "zona-2" in url_l:
        return (3, url)
    if "zona-iii" in url_l or "zona-3" in url_l:
        return (4, url)
    return (9, url)


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
        if day > monthrange(year, mon)[1] and (
            "semua-zona" in slug.lower() or "all-zone" in slug.lower()
        ):
            return date(year, mon, 1)
        return None


def _parse_idr_price(raw: str) -> float | None:
    if not raw:
        return None
    text = str(raw).strip()
    if text in {"-", "--"}:
        return None

    text = text.replace("Rp", "").replace("rp", "").strip()

    # Newer pages use full IDR amounts with thousands separators, e.g. 10.000.
    cleaned_digits = re.sub(r"[^0-9]", "", text.replace(".", "").replace(",", ""))
    if cleaned_digits:
        try:
            price = float(cleaned_digits)
        except ValueError:
            price = None
        if price is not None and 3_000 <= price <= 30_000:
            return price

    # Older pages use shorthand thousands, e.g. 12,90 meaning 12.90 thousand IDR,
    # or 14 meaning 14.00 thousand IDR.
    text_number = text.replace(".", "").replace(",", ".")
    try:
        short_price = float(text_number)
    except ValueError:
        return None
    if 3 <= short_price <= 30:
        price = short_price * 1000
    else:
        price = short_price
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


def _load_pertamina_announcement(page, url: str) -> tuple[list[str], list[list[str]]]:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    except Exception:
        return [], []

    title = (page.title() or "").lower()
    if "404" in title:
        return [], []

    for _ in range(8):
        headers, rows = _extract_pertamina_table(page)
        if headers and rows:
            return headers, rows
        page.wait_for_timeout(1_000)

    return [], []


def _pertamina_has_full_coverage(url: str) -> bool:
    url_l = url.lower()
    return "all-zone" in url_l or "semua-zona" in url_l or "zona" not in url_l


def _extract_pertamina_listing_candidates(page) -> list[tuple[date, str]]:
    seen_urls: set[str] = set()
    candidates: list[tuple[date, str]] = []

    for a in page.locator("a[href]").all():
        href = a.get_attribute("href") or ""
        if "daftar-harga-bahan-bakar-khusus-non-subsidi" not in href:
            continue

        slug = href.split("/")[-1]
        eff_date = _parse_id_slug_date(slug)
        if not eff_date:
            continue

        url = href if href.startswith("http") else f"{_ID_PERTAMINA_NEWS_PREFIX}{slug}"
        if url in seen_urls:
            continue

        seen_urls.add(url)
        candidates.append((eff_date, url))

    return candidates


def _collect_pertamina_listing_candidates(
    page, min_eff_date: date, max_pages: int = 60
) -> list[tuple[date, str]]:
    listing_candidates: list[tuple[date, str]] = []
    seen_signatures: set[tuple[str, ...]] = set()
    seen_urls: set[str] = set()

    for _ in range(max_pages):
        page.wait_for_timeout(2_500)
        page_candidates = _extract_pertamina_listing_candidates(page)
        signature = tuple(url for _, url in page_candidates)
        if not page_candidates or signature in seen_signatures:
            break

        seen_signatures.add(signature)
        for eff_date, url in page_candidates:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            listing_candidates.append((eff_date, url))

        if max(eff_date for eff_date, _ in page_candidates) < min_eff_date:
            break

        next_button = page.locator("button[aria-label='Selanjutnya']").first
        if next_button.count() == 0:
            break

        try:
            next_button.scroll_into_view_if_needed(timeout=5_000)
            next_button.click(timeout=10_000)
        except Exception:
            break

    return listing_candidates


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


