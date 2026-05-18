"""Isle of Man — Office of Fair Trading weekly fuel-monitoring PDF.

Each month a single PDF is published at
``/media/<id>/YYYY-M-<monthname>-road-fuel-monitoring.pdf`` and linked from
``/about-the-government/.../road-fuel-monitoring/``. The index page is behind
an F5/Volterra anti-bot challenge (plain curl gets 403, Wayback returns no
snapshots), so we fetch the index via headless Playwright to harvest the link
and then pull the PDF itself with plain HTTP.

Each PDF contains the rolling ~53 weekly observations (page 2: actual pump
prices including duty & VAT). Older months are not linked anywhere, so the
fetcher only observes the rolling year visible in the latest published PDF.

Output is in pence-per-litre (``GBp``) — the same unit Office of National
Statistics uses for UK retail fuel prices.
"""

import io
import logging
import re
from datetime import date, datetime

import pandas as pd
import pdfplumber

from core.http import make_session

logger = logging.getLogger(__name__)

_INDEX_URL = (
    "https://www.gov.im/about-the-government/statutory-boards/"
    "isle-of-man-office-of-fair-trading/pricing/road-fuel-monitoring/"
)
_PDF_HOST = "https://www.gov.im"
_PDF_LINK_RE = re.compile(r'href="(/media/\d+/[^"]+road-fuel-monitoring\.pdf)"', re.I)
_COUNTRY = "Isle of Man"
# Source publishes pence-per-litre. Emit pounds-per-litre (GBp/100) so the FX
# layer can lookup the standard ISO 4217 code via ExchangerateHost.
_CURRENCY = "GBP"
_PENCE_TO_POUNDS = 0.01
_SOURCE_KEY = "im_oft_weekly"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _discover_pdf_url() -> str:
    """Use a headless Playwright load to extract the latest PDF link."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=_USER_AGENT)
        page = ctx.new_page()
        resp = page.goto(_INDEX_URL, wait_until="domcontentloaded", timeout=30000)
        if resp is None or resp.status != 200:
            browser.close()
            raise RuntimeError(
                f"gov.im index returned status {resp.status if resp else 'none'}"
            )
        html = page.content()
        browser.close()

    m = _PDF_LINK_RE.search(html)
    if not m:
        raise RuntimeError(
            "gov.im index page did not link any road-fuel-monitoring PDF"
        )
    return _PDF_HOST + m.group(1)


def _extract_iom_rows(pdf_bytes: bytes) -> list[dict]:
    """Parse the 'including duty & VAT' table (page 2) for IOM petrol/diesel."""
    rows: list[dict] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        if len(pdf.pages) < 2:
            return rows
        tables = pdf.pages[1].extract_tables()
        if not tables:
            return rows
        table = tables[0]

    # pdfplumber merges the date column and price columns into single cells
    # containing newline-separated values that line up positionally. The first
    # data row is the one whose first cell holds MANY dd/mm/yyyy entries — a
    # header row also matches a single date but is not the series we want.
    data_row = None
    for r in table:
        if r and r[0] and len(re.findall(r"\d{2}/\d{2}/\d{4}", r[0])) >= 5:
            data_row = r
            break
    if data_row is None or len(data_row) < 6:
        return rows

    def _split(cell: str | None) -> list[str]:
        if not cell:
            return []
        return [piece.strip() for piece in cell.split("\n")]

    dates = _split(data_row[0])
    iom_petrol = _split(data_row[2])  # col 2 = IOM petrol (col 1 is UK petrol)
    iom_diesel = _split(data_row[5])  # col 5 = IOM diesel (col 4 is UK diesel)

    for raw_date, petrol_str, diesel_str in zip(dates, iom_petrol, iom_diesel):
        if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", raw_date):
            continue
        try:
            obs = datetime.strptime(raw_date, "%d/%m/%Y").date()
        except ValueError:
            continue
        obs_str = obs.isoformat()
        try:
            petrol_price = float(petrol_str)
        except (TypeError, ValueError):
            petrol_price = None
        try:
            diesel_price = float(diesel_str)
        except (TypeError, ValueError):
            diesel_price = None
        if petrol_price and petrol_price > 0:
            rows.append(
                {
                    "observation_date": obs_str,
                    "country": _COUNTRY,
                    "fuel_product": "Unleaded Petrol",
                    "price_local": petrol_price * _PENCE_TO_POUNDS,
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": "L",
                }
            )
        if diesel_price and diesel_price > 0:
            rows.append(
                {
                    "observation_date": obs_str,
                    "country": _COUNTRY,
                    "fuel_product": "Diesel",
                    "price_local": diesel_price * _PENCE_TO_POUNDS,
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": "L",
                }
            )
    return rows


def fetch_im_oft(cutoff: date) -> pd.DataFrame | None:
    """Fetch Isle of Man weekly fuel prices from the gov.im OFT monthly PDF."""
    pdf_url = _discover_pdf_url()
    logger.info("[im_oft] using PDF %s", pdf_url)

    session = make_session()
    resp = session.get(pdf_url, timeout=120)
    resp.raise_for_status()

    all_rows: list[dict] = []
    for row in _extract_iom_rows(resp.content):
        obs = datetime.strptime(row["observation_date"], "%Y-%m-%d").date()
        if obs <= cutoff:
            continue
        all_rows.append(row)

    if not all_rows:
        return None
    return pd.DataFrame(all_rows)
