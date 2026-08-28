"""ACODECO (Panama) -- statutory Canasta Basica Familiar de Alimentos survey.

ACODECO (Autoridad de Proteccion al Consumidor y Defensa de la Competencia)
publishes a monthly average-price survey of 59 basic-basket food products
across supermarkets in Panama province, as a PDF "compendio" with one very
wide table: rows = products, columns = months (Jan/2015 onward). This is the
statutory "mandated price-comparison list for basic-basket goods" class the
onboarding brief calls out for Panama.

Three real gotchas found while building this:

1. The month-year column headers are rendered REVERSED by whatever tool
   generated the PDF (pdfplumber extracts "51-enE" for what displays as
   "Ene-15" i.e. Jan/2015) -- every header token must be reversed
   (``token[::-1]``) before parsing.
2. The wide table is paginated by COLUMN, not by row: page 1 carries the
   product name + unit + the first ~46 months of prices; pages 2+ repeat
   only the numeric columns for later months, in the SAME row order as page
   1, with no product-name column. Product identity for continuation pages
   is therefore established positionally from the first ("name") page, and
   this fetcher intentionally stops taking rows once it has matched the
   known product count -- ACODECO appends 11 more numeric rows after the 59
   products (category subtotal costs + a "COSTO TOTAL" grand total) that are
   NOT per-product and must not be mistaken for products.
3. www.acodeco.gob.pa serves TLS with an INCOMPLETE certificate chain --
   confirmed via ``openssl s_client -showcerts`` returning only the leaf
   cert (issuer "Go Daddy Secure Certificate Authority - G2", no
   intermediate). macOS/curl verify fine because the OS trust store already
   carries that intermediate; Python's certifi bundle does not, so
   ``requests`` raises CERTIFICATE_VERIFY_FAILED on every call. The fix is to
   supply that intermediate, not to skip verification -- these are the prices
   we ingest, so an unauthenticated transport is a data-integrity hole, not
   just a security one. The intermediate is vendored alongside this module as
   ``_acodeco_gob_pa_chain.pem`` and appended to the certifi bundle.
"""

from __future__ import annotations

import io
import logging
import re
import tempfile
from datetime import date
from functools import lru_cache
from pathlib import Path

import certifi
import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_CHAIN_PEM = Path(__file__).with_name("_acodeco_gob_pa_chain.pem")


@lru_cache(maxsize=1)
def _ca_bundle() -> str:
    bundle = Path(tempfile.gettempdir()) / "acodeco_gob_pa_ca_bundle.pem"
    bundle.write_bytes(
        Path(certifi.where()).read_bytes() + b"\n" + _CHAIN_PEM.read_bytes()
    )
    return str(bundle)


_INDEX_URL = "https://www.acodeco.gob.pa/inicio/estadisticas-precios/precios-2/"
_PDF_LINK_RE = re.compile(r'href="([^"]*Historico_CBA59[^"]*\.pdf)"', re.IGNORECASE)
_COUNTRY = "Panama"
_CURRENCY = (
    "PAB"  # PAB is 1:1 pegged to USD; ACODECO's own table has no currency symbol
)
_SOURCE_KEY = "pa_acodeco_cbfa"

_MESES = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}
_PERIOD_RE = re.compile(r"^([a-zA-Z]{3})-(\d{2})$")
_ROW_RE = re.compile(
    r"^(?P<name>.+?)\s+(?P<qty>\d+(?:\.\d+)?)\s+(?P<unit>[A-Za-zÀ-ÿ]+)\s+(?P<prices>[\d.\s]+)$"
)

_IDENT = ["source_key", "observation_date", "item_name"]


def _parse_period(token: str) -> tuple[int, int] | None:
    m = _PERIOD_RE.match(token[::-1])
    if not m:
        return None
    mon, yy = m.groups()
    mon_num = _MESES.get(mon.lower())
    if not mon_num:
        return None
    return 2000 + int(yy), mon_num


def _discover_pdf_url(session) -> str | None:
    try:
        r = session.get(_INDEX_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] index page fetch failed: %s", _SOURCE_KEY, exc)
        return None
    m = _PDF_LINK_RE.search(r.text)
    if not m:
        logger.warning(
            "[%s] no Historico_CBA59 PDF link found on index page", _SOURCE_KEY
        )
        return None
    href = m.group(1)
    return href if href.startswith("http") else f"https://www.acodeco.gob.pa{href}"


def _find_header_line(lines: list[str]) -> tuple[int, list[tuple[int, int]]] | None:
    for i, line in enumerate(lines):
        tokens = line.split()
        if len(tokens) < 3:
            continue
        parsed = [_parse_period(t) for t in tokens]
        if parsed and all(parsed):
            return i, parsed
    return None


def _parse_pdf(pdf_bytes: bytes) -> list[dict]:
    identity: list[
        tuple[str, str, str]
    ] = []  # (name, qty, unit), established from the first name-page
    period_prices: dict[
        tuple[int, int], list[float]
    ] = {}  # (year, month) -> [price per product, in identity order]

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            found = _find_header_line(lines)
            if not found:
                continue
            header_idx, periods = found
            data_lines = lines[header_idx + 1 :]

            if not data_lines:
                continue
            first_match = _ROW_RE.match(data_lines[0])
            if first_match:
                # Name page: parse name/qty/unit/prices per line, up to the first non-matching line.
                page_rows: list[tuple[str, str, str, list[float]]] = []
                for line in data_lines:
                    m = _ROW_RE.match(line)
                    if not m:
                        break
                    prices = [float(x) for x in m.group("prices").split()]
                    if len(prices) != len(periods):
                        continue
                    page_rows.append(
                        (
                            m.group("name").strip(),
                            m.group("qty"),
                            m.group("unit"),
                            prices,
                        )
                    )
                if not identity:
                    identity = [(n, q, u) for n, q, u, _ in page_rows]
                for idx, period in enumerate(periods):
                    period_prices.setdefault(period, [None] * len(identity))
                    for row_idx, (_, _, _, prices) in enumerate(page_rows):
                        if row_idx < len(identity):
                            period_prices[period][row_idx] = prices[idx]
            else:
                if not identity:
                    logger.warning(
                        "[%s] numeric-only page encountered before product identity was "
                        "established -- skipping page",
                        _SOURCE_KEY,
                    )
                    continue
                # Continuation page: pure-numeric rows, positionally aligned to `identity`,
                # capped at len(identity) to exclude the trailing category-subtotal rows.
                numeric_rows: list[list[float]] = []
                for line in data_lines:
                    tokens = line.split()
                    try:
                        vals = [float(t) for t in tokens]
                    except ValueError:
                        break
                    if len(vals) != len(periods):
                        break
                    numeric_rows.append(vals)
                    if len(numeric_rows) >= len(identity):
                        break
                for idx, period in enumerate(periods):
                    period_prices.setdefault(period, [None] * len(identity))
                    for row_idx, vals in enumerate(numeric_rows):
                        if row_idx < len(identity):
                            period_prices[period][row_idx] = vals[idx]

    if not identity:
        return []

    ts = get_scrape_ts()
    rows: list[dict] = []
    for (year, month), prices in period_prices.items():
        obs_date = date(year, month, 1)
        for row_idx, (name, qty, unit) in enumerate(identity):
            price = prices[row_idx] if row_idx < len(prices) else None
            if price is None or not 0 < price < 1e6:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": name,
                "price_local": round(price, 4),
                "currency": _CURRENCY,
                "unit": f"{qty} {unit}",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)
    return rows


def fetch_pa_acodeco_cbfa(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.verify = (
        _ca_bundle()
    )  # see module docstring gotcha #3: incomplete TLS chain
    pdf_url = _discover_pdf_url(session)
    if not pdf_url:
        return None

    try:
        r = session.get(pdf_url, timeout=60)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] PDF fetch failed: %s", _SOURCE_KEY, exc)
        return None

    rows = _parse_pdf(r.content)
    if not rows:
        return None

    for row in rows:
        row["source_url"] = pdf_url

    df = pd.DataFrame(rows)
    df = df[pd.to_datetime(df["observation_date"]) > pd.Timestamp(cutoff)]
    if df.empty:
        return None
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(df), cutoff)
    return df
