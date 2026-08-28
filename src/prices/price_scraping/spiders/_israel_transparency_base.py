"""Shared base classes for Israel's 2014 Food Price Transparency Law
statutory feeds published over HTTP -- as opposed to the FTPS
publishedprices.co.il portal, which is scaffolded as a fetcher instead (see
src/prices/fetchers/_shared/menaap/israel_publishedprices.py) because
Scrapy's downloader stack does not do FTPS cleanly. Two HTTP portal
families are covered here, both re-verified live 2026-08-06:

- Bina (binaprojects.com): <prefix>.binaprojects.com/MainIO_Hok.aspx lists
  a chain's branch files as JSON; each entry needs a second request to
  Download.aspx?FileNm=<name>, which returns a JSON {"SPath": <real url>}
  redirect target -- a 3-request chain in total.
- PublishPrice (prices.<site_infix>.co.il): a single HTML page embeds the
  day's branch file list as inline JS (`const path = ...; const files =
  [...]`) -- a 2-request chain.

(Shufersal and Super-Pharm use a third HTTP shape, a paginated ASP.NET
WebGrid -- see shufersal_il.py; Super-Pharm's own instance of that shape is
geo-blocked from outside Israel, so it isn't scaffolded here.)

All chains on both families publish the same government-mandated <Item> XML
schema as the FTPS chains (ItemCode, ItemName -- or ItemNm on Bina --,
ItemPrice, UnitOfMeasure). One representative branch per chain, matching
the shufersal_il precedent.

Gotcha verified live 2026-08-06: despite the uniform ".gz" filename
extension, the payload is genuine gzip on some chains (King Store,
Carrefour/Yaynot Bitan) and a zip archive on others (Good Pharm, Zol
VeBegadol) -- detect by magic bytes, never trust the extension.
"""

import gzip
import io
import json
import logging
import re
import zipfile
from datetime import datetime, timezone

import scrapy
from lxml import etree

logger = logging.getLogger(__name__)

_COMMON_SETTINGS = {
    "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    "CONCURRENT_REQUESTS": 1,
    "DOWNLOAD_DELAY": 2.0,
    "RETRY_TIMES": 3,
    "AUTOTHROTTLE_ENABLED": True,
    "USER_AGENT": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _extract_xml(raw: bytes) -> bytes:
    """Detect gzip vs zip by magic bytes -- the ".gz" extension lies on
    some chains (see module docstring)."""
    if raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw)
    if raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            return zf.read(zf.namelist()[0])
    return raw


def _iter_items(xml_bytes: bytes):
    root = etree.fromstring(xml_bytes)
    for item in root.findall(".//Item"):
        code = (item.findtext("ItemCode") or "").strip()
        name = (item.findtext("ItemName") or item.findtext("ItemNm") or "").strip()
        price = (item.findtext("ItemPrice") or "").strip()
        unit = (item.findtext("UnitOfMeasure") or "").strip()
        if code and name and price:
            yield code, name, price, unit


class IsraelTransparencySpiderBase(scrapy.Spider):
    """Common settings + XML-to-item emission. Subclasses implement the
    portal-specific file discovery/download chain and finish by calling
    ``self.emit_items(file_url, response.body)``."""

    currency = "ILS"
    language = "he"
    custom_settings = dict(_COMMON_SETTINGS)

    def emit_items(self, file_url, raw_body):
        xml_bytes = _extract_xml(raw_body)
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for code, name, price, unit in _iter_items(xml_bytes):
            n += 1
            yield {
                "product_id": code,
                "product_name": name[:500],
                "category": unit,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{file_url}#item-{code}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: file={file_url} items={n}")


class BinaTransparencyBase(IsraelTransparencySpiderBase):
    """Bina engine (binaprojects.com). Subclasses set ``bina_prefix`` and
    ``bina_chain_id``."""

    bina_prefix: str = ""
    bina_chain_id: str = ""
    allowed_domains = ["binaprojects.com"]

    async def start(self):
        url = (
            f"https://{self.bina_prefix}.binaprojects.com/MainIO_Hok.aspx"
            f"?_={self.bina_chain_id}&wReshet=%D7%94%D7%9B%D7%9C&WFileType=&WDate=&WStore="
        )
        yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        try:
            entries = json.loads(response.text)
        except json.JSONDecodeError:
            logger.warning(f"{self.name}: listing did not parse as JSON")
            return
        full = sorted(
            e["FileNm"] for e in entries if "pricefull" in e.get("FileNm", "").lower()
        )
        if not full:
            logger.warning(f"{self.name}: no PriceFull entry in listing")
            return
        file_name = full[0]
        base = f"https://{self.bina_prefix}.binaprojects.com"
        resolve_url = f"{base}/Download.aspx?FileNm={file_name}"
        yield scrapy.Request(resolve_url, callback=self.parse_resolve)

    def parse_resolve(self, response):
        try:
            spath = json.loads(response.text)[0]["SPath"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            logger.warning(f"{self.name}: could not resolve SPath from Download.aspx")
            return
        yield scrapy.Request(
            spath, callback=self.parse_pricefile, meta={"file_url": spath}
        )

    def parse_pricefile(self, response):
        yield from self.emit_items(response.meta["file_url"], response.body)


class PublishPriceTransparencyBase(IsraelTransparencySpiderBase):
    """PublishPrice engine (prices.<site_infix>.co.il). Subclasses set
    ``site_infix``."""

    site_infix: str = ""
    _FILES_RE = re.compile(r"const files = (\[.*?\]);", re.S)
    _PATH_RE = re.compile(r"const path = ['\"]([^'\"]+)['\"]")

    async def start(self):
        yield scrapy.Request(
            f"https://prices.{self.site_infix}.co.il/", callback=self.parse_listing
        )

    def parse_listing(self, response):
        files_m = self._FILES_RE.search(response.text)
        path_m = self._PATH_RE.search(response.text)
        if not files_m or not path_m:
            logger.warning(f"{self.name}: embedded files/path script not found")
            return
        try:
            files = json.loads(files_m.group(1))
        except json.JSONDecodeError:
            logger.warning(f"{self.name}: files array did not parse as JSON")
            return
        path = path_m.group(1)
        full = sorted(
            f["name"] for f in files if "pricefull" in f.get("name", "").lower()
        )
        if not full:
            logger.warning(f"{self.name}: no PriceFull entry in listing")
            return
        file_name = full[0]
        base = f"https://prices.{self.site_infix}.co.il"
        file_url = f"{base}/{path}/{file_name}"
        yield scrapy.Request(
            file_url, callback=self.parse_pricefile, meta={"file_url": file_url}
        )

    def parse_pricefile(self, response):
        yield from self.emit_items(response.meta["file_url"], response.body)
