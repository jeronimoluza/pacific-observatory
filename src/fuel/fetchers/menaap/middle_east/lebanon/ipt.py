"""IPT Lebanon fetcher: Selenium-driven xlsx export from Sub.aspx?pageid=22.

The page is an ASP.NET WebForms host for a Telerik RadHtmlChart wrapped in a
RadAjaxPanel. Clicking "Export" triggers an asynchronous postback whose
response includes a `RegisterStartupScript` call to `downloadFile()` that
sets `aExport.href` and navigates the browser to a dynamically generated
xlsx URL. We could not reliably replicate that handshake from raw `requests`
(the server rejects naive POSTs and full AJAX delta postbacks require
Telerik-specific TSM tokens), so we drive a headless Chrome via Selenium:
GET the page, click the "All" date-range filter, click Export, wait for the
xlsx to land, and parse it.

Wide-format xlsx schema:
    Date | Octane98 | Octane95 | Diesel | GasOil | Gas

`GasOil` is unmapped (the chart legend never shows it). We log a WARNING when
a `GasOil` cell is non-empty so divergence is loud.

Numeric cells arrive as comma-formatted strings or numbers; we coerce with
`_coerce_price`.
"""

from __future__ import annotations

import io
import logging
import shutil
import tempfile
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_PAGE_URL = "https://www.iptgroup.com.lb/Sub.aspx?pageid=22"

_COUNTRY = "Lebanon"
_CURRENCY = "LBP"
_SOURCE_KEY = "ipt_weekly"

_EXPECTED_COLUMNS = ["Date", "Octane98", "Octane95", "Diesel", "GasOil", "Gas"]

# xlsx header → output `fuel_product` value (matches keys in ipt.yaml products)
_PRODUCT_MAP = {
    "Octane98": "UNL 98",
    "Octane95": "UNL 95",
    "Diesel": "Diesel",
    "Gas": "Gas (LPG)",
}

_LBTN_FILTER_ALL_ID = "phBody_phSlaveBody_BICMSZone1_ctl00_ctl00_lbtnFilterAll"
_LBTN_EXPORT_ID = "phBody_phSlaveBody_BICMSZone1_ctl00_ctl00_lbtnExport"

_DOWNLOAD_TIMEOUT_SECONDS = 90


def _coerce_date(value) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.date()


def _coerce_price(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        if value <= 0:
            return None
        return float(value)
    text = str(value).strip().replace(",", "").replace("L.L.", "").strip()
    if not text:
        return None
    try:
        price = float(text)
    except ValueError:
        return None
    if price <= 0:
        return None
    return price


def _parse_xlsx(payload: bytes) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(payload), dtype=object)
    columns = list(df.columns)
    if columns != _EXPECTED_COLUMNS:
        raise RuntimeError(
            f"IPT xlsx schema drift: expected columns {_EXPECTED_COLUMNS}, got {columns}"
        )
    return df


def _emit_rows(df: pd.DataFrame, cutoff: date) -> list[dict]:
    rows: list[dict] = []
    for record in df.to_dict(orient="records"):
        obs_date = _coerce_date(record.get("Date"))
        if obs_date is None:
            continue
        if obs_date <= cutoff:
            continue

        gasoil_value = record.get("GasOil")
        if gasoil_value not in (None, "") and not (
            isinstance(gasoil_value, float) and pd.isna(gasoil_value)
        ):
            logger.warning(
                "IPT xlsx has non-empty GasOil cell on %s: %r — column is unmapped, value ignored",
                obs_date.isoformat(),
                gasoil_value,
            )

        emitted_for_date = 0
        for raw_col, canonical in _PRODUCT_MAP.items():
            price = _coerce_price(record.get(raw_col))
            if price is None:
                continue
            rows.append(
                {
                    "observation_date": obs_date.isoformat(),
                    "country": _COUNTRY,
                    "fuel_product": canonical,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": "L",
                    "source_key": _SOURCE_KEY,
                }
            )
            emitted_for_date += 1
        if emitted_for_date == 0:
            logger.debug(
                "IPT row %s has no parseable product prices — skipped", obs_date
            )
    return rows


def _download_xlsx_via_selenium() -> bytes:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    download_dir = Path(tempfile.mkdtemp(prefix="ipt_dl_"))
    chrome_opts = Options()
    chrome_opts.add_argument("--headless=new")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--window-size=1280,1024")
    chrome_opts.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )
    driver = webdriver.Chrome(options=chrome_opts)
    try:
        driver.get(_PAGE_URL)
        wait = WebDriverWait(driver, 30)
        filter_all = wait.until(
            EC.element_to_be_clickable((By.ID, _LBTN_FILTER_ALL_ID))
        )
        filter_all.click()
        time.sleep(1.5)
        export_btn = wait.until(EC.element_to_be_clickable((By.ID, _LBTN_EXPORT_ID)))
        export_btn.click()

        deadline = time.time() + _DOWNLOAD_TIMEOUT_SECONDS
        xlsx_path: Path | None = None
        while time.time() < deadline:
            candidates = sorted(
                [p for p in download_dir.iterdir() if p.suffix.lower() == ".xlsx"],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            partials = [
                p for p in download_dir.iterdir() if p.name.endswith(".crdownload")
            ]
            if candidates and not partials:
                xlsx_path = candidates[0]
                break
            time.sleep(1)
        if xlsx_path is None:
            listing = sorted(p.name for p in download_dir.iterdir())
            raise RuntimeError(
                f"IPT xlsx download did not complete within {_DOWNLOAD_TIMEOUT_SECONDS}s; "
                f"download dir contents: {listing}"
            )
        return xlsx_path.read_bytes()
    finally:
        driver.quit()
        shutil.rmtree(download_dir, ignore_errors=True)


def fetch_ipt(cutoff: date) -> pd.DataFrame | None:
    """Fetch Lebanon fuel prices from IPT's xlsx export.

    Returns a DataFrame with rows strictly after `cutoff`, or `None` if no
    new observations are available.
    """
    payload = _download_xlsx_via_selenium()
    df = _parse_xlsx(payload)
    rows = _emit_rows(df, cutoff)
    logger.info(
        "IPT xlsx: %d rows after cutoff %s (from %d xlsx rows)",
        len(rows),
        cutoff,
        len(df),
    )
    if not rows:
        return None
    return pd.DataFrame(rows)


def parse_xlsx_payload(payload: bytes, cutoff: date) -> pd.DataFrame | None:
    """Test-friendly entrypoint: parse xlsx bytes without performing HTTP."""
    df = _parse_xlsx(payload)
    rows = _emit_rows(df, cutoff)
    if not rows:
        return None
    return pd.DataFrame(rows)


__all__ = ["fetch_ipt", "parse_xlsx_payload"]
