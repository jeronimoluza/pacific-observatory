"""Shanghai DRC daily main food price monitor.

Shanghai Municipal Development and Reform Commission publishes daily pages
with a legacy ``.xls`` attachment containing citywide average and store-level
prices for staple foods. This fetcher emits the attachment's citywide average
row only, one observation per product/date.

The attachment is BIFF ``.xls``. The project environment does not carry an
``xlrd`` dependency, so this fetcher uses a local LibreOffice/soffice binary to
convert the workbook to CSV before parsing it.
"""

from __future__ import annotations

import csv
import logging
import re
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_INDEX_URL = "https://fgw.sh.gov.cn/fgw_jgjgdt/index.html"
_COUNTRY = "China"
_SUBNATIONAL_AREA = "Shanghai"
_CURRENCY = "CNY"
_SOURCE_KEY = "cn_shanghai_fgw_food_prices"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]
_DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


def _parse_cn_date(text: str) -> date | None:
    match = _DATE_RE.search(text or "")
    if not match:
        return None
    year, month, day = match.groups()
    return date(int(year), int(month), int(day))


def _latest_article(session) -> tuple[str, date] | None:
    resp = session.get(_INDEX_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    for link in soup.find_all("a", href=True):
        title = link.get_text(" ", strip=True)
        if "主要主副食品品种价格信息表" not in title:
            continue
        obs_date = _parse_cn_date(title)
        if obs_date is None:
            continue
        return urljoin(_INDEX_URL, link["href"]), obs_date
    return None


def _attachment_url(session, article_url: str) -> str | None:
    resp = session.get(article_url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    for link in soup.find_all("a", href=True):
        href = link["href"]
        label = link.get_text(" ", strip=True)
        if href.lower().endswith(".xls") and "价格信息表" in label:
            return urljoin(article_url, href)
    return None


def _download_and_convert(session, xls_url: str) -> list[list[str]]:
    soffice = shutil.which("soffice")
    if not soffice:
        raise RuntimeError("soffice not found; needed to convert Shanghai .xls")

    with tempfile.TemporaryDirectory(prefix="shanghai_fgw_") as tmp:
        tmpdir = Path(tmp)
        xls_path = tmpdir / "source.xls"
        csv_path = tmpdir / "source.csv"
        resp = session.get(xls_url, timeout=60)
        resp.raise_for_status()
        xls_path.write_bytes(resp.content)
        subprocess.run(
            [soffice, "--headless", "--convert-to", "csv", "--outdir", tmp, xls_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
        )
        if not csv_path.exists():
            raise RuntimeError(f"soffice conversion did not create {csv_path}")
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.reader(f))


def _find_row(rows: list[list[str]], label: str) -> list[str]:
    for row in rows:
        if row and row[0].strip() == label:
            return row
    raise LookupError(f"row label not found in Shanghai attachment: {label}")


def _num(value: str) -> float | None:
    text = str(value or "").strip()
    if not text or text == "-":
        return None
    try:
        price = float(text)
    except ValueError:
        return None
    return price if price > 0 else None


def _parse_rows(rows: list[list[str]], obs_date: date, source_url: str) -> list[dict]:
    categories = _find_row(rows, "类别")
    products = _find_row(rows, "品种")
    specs = _find_row(rows, "规格")
    units = _find_row(rows, "单位")
    averages = _find_row(rows, "均价")

    scrape_ts = get_scrape_ts()
    parsed: list[dict] = []
    for idx in range(2, len(averages)):
        price = _num(averages[idx])
        if price is None:
            continue
        product = products[idx].strip() if idx < len(products) else ""
        unit = units[idx].strip() if idx < len(units) else ""
        if not product or not unit:
            continue
        spec = specs[idx].strip() if idx < len(specs) else ""
        category = categories[idx].strip() if idx < len(categories) else ""
        item_name = f"{product}, {spec}" if spec else product
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "daily",
            "country": _COUNTRY,
            "subnational_area": _SUBNATIONAL_AREA,
            "source_key": _SOURCE_KEY,
            "coicop_code": None,
            "item_name": item_name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": source_url,
            "notes": f"citywide average; category={category or 'n/a'}",
            "scrape_ts": scrape_ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        parsed.append(row)
    return parsed


def fetch_cn_shanghai_fgw_food_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    latest = _latest_article(session)
    if latest is None:
        logger.warning("[%s] no daily price article found at %s", _SOURCE_KEY, _INDEX_URL)
        return None
    article_url, obs_date = latest
    if obs_date <= cutoff:
        logger.info("[%s] latest date %s <= cutoff %s", _SOURCE_KEY, obs_date, cutoff)
        return None

    xls_url = _attachment_url(session, article_url)
    if not xls_url:
        logger.warning("[%s] no .xls attachment found at %s", _SOURCE_KEY, article_url)
        return None

    rows = _parse_rows(_download_and_convert(session, xls_url), obs_date, article_url)
    logger.info("[%s] parsed %d rows for %s", _SOURCE_KEY, len(rows), obs_date)
    return pd.DataFrame(rows) if rows else None
