"""Shared FTPS client for Israel's Food Price Transparency Law statutory
feeds published through the publishedprices.co.il aggregator portal (the
"Cerberus" platform in the open-source il-supermarket-scraper project this
was cross-checked against). Israel's 2014 law requires every retail chain
with 3+ branches to publish a machine-readable full-catalog snapshot at
least daily; roughly a dozen chains publish theirs through this one shared
FTPS login rather than a dedicated web portal (contrast with Shufersal /
Carrefour / the *.binaprojects.com chains, which are HTTP and use the spider
base at price_scraping/spiders/_israel_transparency_base.py instead).

One chain = one FTP login (per-chain username, published openly by the
government; password is blank or trivial for most chains). Each login lists
a flat directory of gzip/zip-XML per-branch catalog snapshots named
Price<chainID>-...-<store>-<date>-<time>.gz (hourly deltas) and
PriceFull<chainID>-...-<store>-<date>-<time>.gz (full catalog per branch).
This module always targets a PriceFull file -- one representative branch,
mirroring the precedent set by the shipped shufersal_il spider -- never the
whole chain (dozens to hundreds of branches) and never the incremental
Price deltas.

Verified live 2026-08-06 against 8 chains (RamiLevi, TivTaam, yohananof,
doralon, Paz_bo/Yellow, Keshet, Stop_Market, yuda_ho/SuperYuda): all
returned real Hebrew grocery/convenience items with plausible ILS prices.
Two logins probed and rejected: osherad and SuperCofixApp authenticate but
list Stores-only directories with zero Price/PriceFull files -- the gov.il
register shows Cofix folded into Rami Levy's own feed as of 2026-08-04;
Osher Ad's dedicated feed is presumed similarly retired. Do not re-add
those two without re-checking the gov.il register first.

Gotcha: despite the uniform ".gz" extension, the payload is gzip on some
chains (Rami Levy, Carrefour, King Store) and a zip archive on others (Good
Pharm, Zol VeBegadol) -- detect by magic bytes, never trust the extension.
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import date, datetime, timezone
from ftplib import FTP_TLS

import pandas as pd
from lxml import etree

from prices.fetchers.utils import make_hash

try:
    import gzip
except ImportError:  # pragma: no cover - stdlib, always present
    gzip = None

logger = logging.getLogger(__name__)

_FTP_HOST = "url.retail.publishedprices.co.il"
_COUNTRY = "Israel"
_CURRENCY = "ILS"
_IDENT = ["source_key", "observation_date", "source_url"]
_DATE_RE = re.compile(r"(20\d{6})")


def _extract_xml(raw: bytes) -> bytes:
    """Government feeds are inconsistently gzip vs zip despite the uniform
    ".gz" name -- detect by magic bytes rather than trusting the extension."""
    if raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw)
    if raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            return zf.read(zf.namelist()[0])
    return raw


def _date_from_filename(name: str) -> date | None:
    m = _DATE_RE.search(name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def _list_files(ftp: FTP_TLS) -> list[tuple[str, dict]]:
    try:
        return list(ftp.mlsd())
    except Exception:  # noqa: BLE001 - server doesn't support MLSD
        return [(n, {"type": "file"}) for n in ftp.nlst()]


def fetch_publishedprices_chain(
    *,
    source_key: str,
    ftp_username: str,
    cutoff: date,
    ftp_password: str = "",
    ftp_path: str = "/",
) -> pd.DataFrame | None:
    """Connect to the shared publishedprices.co.il FTPS portal for one
    statutory chain login, pick one representative branch's most recent
    PriceFull (full-catalog) snapshot, and emit PriceObservation rows.
    ``item_name``/``price_local`` feed the classifier corpus per
    ``src/prices/enrich/stages/concatenate.py:_emit_price_obs`` -- this
    fetcher never populates ``coicop_code`` itself.
    """
    try:
        ftp = FTP_TLS(_FTP_HOST, ftp_username, ftp_password, timeout=60)
        ftp.trust_server_pasv_ipv4_address = True
        ftp.prot_p()
        ftp.cwd(ftp_path)
        entries = _list_files(ftp)
    except Exception:
        logger.exception(
            "publishedprices: FTP login/listing failed for %s (user=%s)",
            source_key,
            ftp_username,
        )
        return None

    full_files = sorted(
        name
        for name, facts in entries
        if facts.get("type") == "file" and "pricefull" in name.lower()
    )
    if not full_files:
        logger.warning(
            "publishedprices: no PriceFull file for %s (%d entries listed)",
            source_key,
            len(entries),
        )
        ftp.quit()
        return None

    file_name = full_files[0]
    obs_date = _date_from_filename(file_name) or date.today()
    if obs_date <= cutoff:
        ftp.quit()
        logger.info(
            "publishedprices: %s snapshot %s <= cutoff %s, nothing new",
            source_key,
            obs_date,
            cutoff,
        )
        return None

    buf = io.BytesIO()
    try:
        ftp.retrbinary(f"RETR {file_name}", buf.write)
    finally:
        ftp.quit()

    xml_bytes = _extract_xml(buf.getvalue())
    root = etree.fromstring(xml_bytes)
    items = root.findall(".//Item")
    if not items:
        logger.warning(
            "publishedprices: %s file %s parsed 0 items", source_key, file_name
        )
        return None

    scrape_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    file_url = f"ftp://{_FTP_HOST}{ftp_path.rstrip('/') or '/'}/{file_name}"

    rows = []
    for item in items:
        code = (item.findtext("ItemCode") or "").strip()
        name = (item.findtext("ItemName") or item.findtext("ItemNm") or "").strip()
        price_raw = (item.findtext("ItemPrice") or "").strip()
        unit = (item.findtext("UnitOfMeasure") or "").strip()
        if not code or not name or not price_raw:
            continue
        try:
            price = float(price_raw)
        except ValueError:
            continue
        if price <= 0:
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": source_key,
            "coicop_code": None,
            "item_name": name[:500],
            "price_local": price,
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": f"{file_url}#{code}",
            "notes": "",
            "scrape_ts": scrape_ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        return None
    logger.info(
        "publishedprices: %s branch file %s -> %d items",
        source_key,
        file_name,
        len(rows),
    )
    return pd.DataFrame(rows)
