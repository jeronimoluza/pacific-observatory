"""Philippines DOE NCR retail pump price fetcher."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_philippines_doe",
        "country": "Philippines",
        "source_name": "DOE NCR Retail Pump Prices",
        "url": "https://doe.gov.ph/articles/3142895--list-of-ncr-pump-prices",
        "description": "Official government source (Philippines Department of Energy). "
        "Publishes weekly NCR retail pump price monitoring reports as PDF. "
        "Summary table on last page contains Common Price for 6 products.",
        "extraction_method": [
            "Web scraping (__NUXT__ payload)",
            "PDF parsing (pdfplumber)",
        ],
        "products": [
            "Gasoline (RON97/100)",
            "Gasoline (RON95)",
            "Gasoline (RON91)",
            "Diesel",
            "Diesel Plus",
            "Kerosene",
        ],
        "source_keys": ["ph_doe_retail_pump_prices"],
        "frequency": "Weekly",
        "publishes_on": "Tuesday",
        "notes": "Summary table present from Jul 2023 onward. "
        "~270 PDFs listed on a single article page. "
        "PDF URLs extracted from __NUXT__ JS payload.",
    },
]

import io
import re
import time
from datetime import date, timedelta

import pandas as pd

from ..utils import MONTH_MAP_EN, get_session, make_hash, make_template

# ── Template ─────────────────────────────────────────────────────────────────

_NCR_LISTING_URL = "https://doe.gov.ph/articles/3142895--list-of-ncr-pump-prices"

_TMPL = make_template(
    country="Philippines",
    wb_iso3="PHL",
    source_key="ph_doe_retail_pump_prices",
    source_name="Philippines DOE NCR Retail Pump Prices",
    source_url=_NCR_LISTING_URL,
    currency="PHP",
    unit="L",
    subnational_area="NCR",
    publication_frequency="weekly",
    observation_method="survey",
)

# ── Product mapping ──────────────────────────────────────────────────────────
# PDF product name → (fuel_family, fuel_product, quality_group, octane_ron)

_PRODUCT_MAP: dict[str, tuple[str, str, str, int | None]] = {
    "Gasoline (RON97/100)": ("gasoline", "RON 97/100", "premium", 100),
    "Gasoline (RON95)": ("gasoline", "RON 95", "premium", 95),
    "Gasoline (RON91)": ("gasoline", "RON 91", "regular", 91),
    "Diesel": ("diesel", "Diesel", "regular", None),
    "Diesel Plus": ("diesel", "Diesel Plus", "premium", None),
    "Kerosene": ("kerosene", "Kerosene", "regular", None),
}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _extract_ncr_pdf_urls(html: str) -> list[str]:
    """Extract NCR price monitoring PDF URLs from __NUXT__ payload."""
    paths = re.findall(
        r"documents(?:\\u002F|/)d(?:\\u002F|/)([a-zA-Z0-9_-]+)(?:\\u002F|/)([a-zA-Z0-9_.:-]+)",
        html,
    )
    urls: list[str] = []
    seen: set[str] = set()
    for group, name in paths:
        if not re.search(r"ncr|petro", name, re.IGNORECASE):
            continue
        full = f"https://prod-cms.doe.gov.ph/documents/d/{group}/{name}"
        if full not in seen:
            seen.add(full)
            urls.append(full)
    return urls


def _parse_date_from_title(title: str) -> date | None:
    """Parse week-start date from summary table title.

    Handles: 'PREVAILING ... NCR\\n(for the week of March 31 - April 6, 2026)'
    """
    m = re.search(
        r"week\s+of\s+(\w+)\s+(\d{1,2})\s*[-–]\s*\w+\s+\d{1,2}\s*,?\s*(\d{4})",
        title,
        re.IGNORECASE,
    )
    if m:
        month = MONTH_MAP_EN.get(m.group(1).lower()[:3])
        if month:
            try:
                return date(int(m.group(3)), month, int(m.group(2)))
            except ValueError:
                pass

    # Fallback: just find month + day + year anywhere
    m = re.search(
        r"(\w+)\s+(\d{1,2})\s*[-–,].*?(\d{4})",
        title,
        re.IGNORECASE,
    )
    if m:
        month = MONTH_MAP_EN.get(m.group(1).lower()[:3])
        if month:
            try:
                return date(int(m.group(3)), month, int(m.group(2)))
            except ValueError:
                pass
    return None


def _parse_ncr_summary_table(
    content: bytes,
) -> tuple[date | None, list[dict]]:
    """Extract Common Price rows from the NCR summary table in a PDF.

    Returns (observation_date, [{product, price}, ...]).
    """
    try:
        import pdfplumber
    except ImportError:
        print("  [ph_doe] pdfplumber not installed")
        return None, []

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    if not table or len(table) < 3:
                        continue
                    header_text = str(table[0][0] or "").upper()
                    if "PREVAILING" not in header_text:
                        continue

                    # Parse date from title row
                    obs_date = _parse_date_from_title(str(table[0][0] or ""))

                    # Extract product → common_price pairs
                    rows: list[dict] = []
                    for row in table[2:]:  # skip title + header rows
                        if not row or not row[0]:
                            continue
                        product = str(row[0]).strip()
                        price_raw = str(row[-1] or "").strip()
                        if not price_raw or price_raw in ("#N/A", "N/A", "-", ""):
                            continue
                        try:
                            price = float(re.sub(r"[^\d.]", "", price_raw))
                        except ValueError:
                            continue
                        if not (30 <= price <= 300):
                            continue
                        rows.append({"product": product, "price": round(price, 2)})

                    return obs_date, rows
    except Exception as e:
        print(f"  [ph_doe] PDF parse error: {e}")

    return None, []


# ── Main fetcher ─────────────────────────────────────────────────────────────


def fetch_philippines_doe(cutoff: date) -> pd.DataFrame:
    """Fetch Philippines DOE NCR retail pump prices from weekly PDFs."""
    print("  [ph_doe] Fetching Philippines DOE NCR data...")
    print(f"  [ph_doe] Cutoff: {cutoff}")

    session = get_session()
    today = date.today()

    # 1. Fetch listing page and extract PDF URLs
    try:
        resp = session.get(_NCR_LISTING_URL, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [ph_doe] Could not fetch listing page: {e}")
        return pd.DataFrame()

    pdf_urls = _extract_ncr_pdf_urls(resp.text)
    print(f"  [ph_doe] Found {len(pdf_urls)} PDF URLs")

    if not pdf_urls:
        print("  [ph_doe] No PDF URLs found")
        return pd.DataFrame()

    # 2. Download each PDF, parse summary table, build rows
    #    URLs are newest-first; stop after enough consecutive old/unparseable PDFs.
    all_rows: list[dict] = []
    skipped = 0
    consecutive_old = 0

    for pdf_url in pdf_urls:
        try:
            pr = session.get(pdf_url, timeout=30)
            if pr.status_code != 200:
                continue
        except Exception as e:
            print(f"  [ph_doe] Download error {pdf_url}: {e}")
            time.sleep(0.3)
            continue

        obs_date, products = _parse_ncr_summary_table(pr.content)

        if obs_date is None or not products:
            skipped += 1
            consecutive_old += 1
            if consecutive_old >= 8:
                print("  [ph_doe] Stopping: 8 consecutive PDFs without summary table")
                break
            time.sleep(0.3)
            continue

        if obs_date <= cutoff or obs_date > today:
            consecutive_old += 1
            if consecutive_old >= 8:
                print("  [ph_doe] Stopping: 8 consecutive PDFs at or before cutoff")
                break
            time.sleep(0.3)
            continue

        consecutive_old = 0

        rows_added = 0
        for prod in products:
            mapped = _PRODUCT_MAP.get(prod["product"])
            if mapped is None:
                continue
            family, fuel_product, qg, ron = mapped

            r = _TMPL.copy()
            r.update(
                {
                    "fuel_family": family,
                    "fuel_product": fuel_product,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "price_local": prod["price"],
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date + timedelta(days=6)),
                    "observation_date": str(obs_date),
                    "source_url": pdf_url,
                }
            )
            r["observation_hash"] = make_hash(r)
            all_rows.append(r)
            rows_added += 1

        if rows_added:
            print(f"  [ph_doe] {obs_date}: {rows_added} products")
        time.sleep(0.3)

    if skipped:
        print(f"  [ph_doe] Skipped {skipped} PDFs (no summary table or no date)")
    if all_rows:
        print(f"  [ph_doe] Total: {len(all_rows)} new rows")
    else:
        print("  [ph_doe] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
