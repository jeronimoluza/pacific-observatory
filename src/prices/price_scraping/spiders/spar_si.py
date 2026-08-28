"""
Spider for Spar Slovenia — https://online.spar.si/.

Next.js App Router storefront. Category pages carry no `__NEXT_DATA__`
script (that's the Pages Router pattern) -- instead the product catalog
streams in via React Server Component payloads
(`<script>self.__next_f.push([1,"..."])</script>`, App Router's hydration
mechanism), each chunk holding a JS-string-escaped fragment of a flattened
object graph. Rather than reconstructing the full graph, a bounded regex
pulls each `CatalogProductModel`'s `name`, `price`, `sku` and `slug`
directly out of the escaped JSON text -- robust because those four keys
always appear in that order within one product's fragment.

Re-verified live 2026-08-06: GET
/ca/sadje-in-zelenjava/sveza-zelenjava/krompir/S1/S1-1/S1-1-2 -> 200, 930KB,
23 real products incl. 'GORENJSKI KROMPIR, SPAR, 3KG' EUR 2.99 (sku
493603), 'SLADKI KROMPIR, TEHTANO' EUR 2.49. Category URLs (`/ca/<slug.../
S<n>[-<n>...]`) come from /sitemap-categories.xml (668 total); the crawl
list here (`_spar_si_categories.txt`, 535 entries) keeps only S-codes with
no child S-code in the sitemap (e.g. S1-1-2 has no S1-1-2-* sibling), i.e.
leaf categories.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://online.spar.si"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_spar_si_categories.txt"
_PRODUCT_RE = re.compile(
    r'\\"name\\":\\"([^"\\]+)\\",\\"price\\":([0-9.]+),'
    r'(?:(?!\\"name\\").)*?'
    r'\\"sku\\":\\"([^"\\]+)\\"'
    r'(?:(?!\\"name\\").)*?'
    r'\\"slug\\":\\"([^"\\]+)\\"',
    re.S,
)


def _load_categories():
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class SparSiSpider(scrapy.Spider):
    name = "spar_si"
    allowed_domains = ["online.spar.si"]
    currency = "EUR"
    language = "sl"

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
        for path in _load_categories():
            yield scrapy.Request(
                f"{_BASE}/{path}",
                callback=self.parse_page,
                meta={"path": path},
            )

    def parse_page(self, response):
        path = response.meta["path"]
        matches = _PRODUCT_RE.findall(response.text)
        if not matches:
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen = set()
        count = 0
        for name, price, sku, slug in matches:
            if sku in seen:
                continue
            seen.add(sku)
            count += 1
            yield {
                "product_id": sku,
                "product_name": name.strip()[:500],
                "category": path.split("/")[1] if "/" in path else path,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}/p/{slug}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"spar_si: {path} items={count}")
