"""
Spider for Shufersal (Israel) — https://prices.shufersal.co.il/.

Israel's 2014 Food Price Transparency Law requires every supermarket chain
with 3+ branches to publish a machine-readable snapshot of its full catalog
(name, barcode, price, unit) at least daily. Shufersal (Israel's largest
chain) publishes one gzip-compressed XML file per branch at
prices.shufersal.co.il; the homepage's paginated ASP.NET WebGrid lists every
branch's current file as a short-lived (same-day) Azure Blob SAS-signed URL,
re-resolved on each run rather than hardcoded.

This spider targets store 001 (present on page 1 of the listing, StoreID
"001") as a representative single-branch snapshot -- assortment is
near-identical across branches of the same chain, and the portal is
architected per-branch (no whole-chain file), so one branch is the natural
unit here.

Re-verified live 2026-08-06: GET / -> HTTP 200, page 1 of an 85-page grid
(20 rows/page) lists store 001's Price*.gz (~2KB gz). Downloaded and
parsed: real Hebrew grocery items, e.g. 'שזיף אבטיח לב אדום 5.5' (plum) ILS
14.90, 'מלון גולדן סוויט' (melon). XML schema: Root > Items > Item >
ItemCode/ItemName/ItemPrice/UnitOfMeasure/ManufactureCountry. Currency ILS
(law-mandated, matches countries.yaml).
"""

import gzip
import logging
import re
from datetime import datetime, timezone

import scrapy
from lxml import etree

logger = logging.getLogger(__name__)

_BASE = "https://prices.shufersal.co.il"
_STORE_ID = "001"
# catID=2 is the "PricesFull" category in the portal's #ddlCategory select;
# storeId=1 is store 001. The bare homepage grid lists ONLY the hourly
# `Price` DELTAS (a ~2 KB file, 33 items) -- reading it is why this spider
# used to contribute 11 observations for Israel's largest chain. The full
# catalog lives under a different blob container (/pricefull/, not /price/)
# and is only listed by this AJAX endpoint (Scripts/Main.js binds it to the
# category dropdown). Verified live 2026-09-05: 326 KB gz, 22k+ items.
_LISTING = f"{_BASE}/FileObject/UpdateCategory?catID=2&storeId=1"
_FILE_RE = re.compile(
    r'href="(https://pricesprodpublic\.blob\.core\.windows\.net/pricefull/'
    r"PriceFull\d+-\d+-" + _STORE_ID + r'-\d+-\d+\.gz\?[^"]+)"'
)
# "unknown" placeholder the statutory schema uses for an absent field.
_UNKNOWN = "לא ידוע"


def _declared_quantity(item) -> str:
    """The item's PACKAGE size as "<Quantity> <UnitQty>" -- NOT UnitOfMeasure,
    which is the basis unit of UnitOfMeasurePrice ("100 גרם") rather than the
    pack ItemPrice refers to. See the same helper in
    ``_israel_transparency_base.py``."""
    qty = (item.findtext("Quantity") or "").strip()
    unit_qty = (item.findtext("UnitQty") or "").strip()
    if not qty or not unit_qty or unit_qty == _UNKNOWN:
        return ""
    try:
        if float(qty) <= 0:
            return ""
    except ValueError:
        return ""
    return f"{qty} {unit_qty}"


class ShufersalIlSpider(scrapy.Spider):
    name = "shufersal_il"
    allowed_domains = [
        "prices.shufersal.co.il",
        "pricesprodpublic.blob.core.windows.net",
    ]
    currency = "ILS"
    language = "he"

    custom_settings = {
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

    async def start(self):
        yield scrapy.Request(
            _LISTING,
            callback=self.parse_listing,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{_BASE}/",
            },
        )

    def parse_listing(self, response):
        m = _FILE_RE.search(response.text)
        if not m:
            logger.warning(
                "shufersal_il: store %s PriceFull link not found in the "
                "catID=2 listing",
                _STORE_ID,
            )
            return
        file_url = m.group(1).replace("&amp;", "&")
        yield scrapy.Request(file_url, callback=self.parse_pricefile)

    def parse_pricefile(self, response):
        try:
            xml_bytes = gzip.decompress(response.body)
        except OSError:
            xml_bytes = response.body
        root = etree.fromstring(xml_bytes)
        items = root.findall(".//Item")
        logger.info(f"shufersal_il: store={_STORE_ID} items={len(items)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for item in items:
            code = (item.findtext("ItemCode") or "").strip()
            name = (item.findtext("ItemName") or "").strip()
            price = (item.findtext("ItemPrice") or "").strip()
            unit = (item.findtext("UnitOfMeasure") or "").strip()
            if not code or not name or not price:
                continue
            yield {
                "product_id": code,
                "product_name": name[:500],
                "category": unit,
                "unit": _declared_quantity(item),
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}/#item-{code}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
