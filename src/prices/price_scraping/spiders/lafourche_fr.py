"""
Spider for La Fourche (France) — https://lafourche.fr/.

Next.js storefront on Shopify, but the native Shopify /products.json and
/collections/<h>/products.json endpoints are not proxied (404 -> the app's
own 404 page). The full catalog IS reachable server-rendered, though: the
"all products" collection page embeds an Algolia-backed hydration payload
in __NEXT_DATA__ (props.pageProps.searchServerState.initialResults) with
clean per-product hits (id, sku, handle, title, price, inventory_available).

Re-verified live 2026-08-06: GET /collections/all -> 200, 1.85MB,
__NEXT_DATA__ present, nbHits=4842, nbPages=25, hitsPerPage=40. GET
/collections/all?page=2 returns a different, non-overlapping page of hits
(confirms the ?page= param drives real pagination). Sample hit: 'Olives
Kalamata dénoyautées bio' price=2.87 EUR.
"""

import html as htmlmod
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://lafourche.fr"
MAX_PAGES = 40  # safety cap, above the observed nbPages=25

_NEXT_DATA_RE = re.compile(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


class LafourcheFrSpider(scrapy.Spider):
    name = "lafourche_fr"
    allowed_domains = ["lafourche.fr"]
    currency = "EUR"
    language = "fr"

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
            f"{_BASE}/collections/all?page=1",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def _extract_hits(self, response):
        match = _NEXT_DATA_RE.search(response.text)
        if not match:
            logger.warning(f"lafourche_fr: no __NEXT_DATA__ at {response.url}")
            return [], None
        try:
            data = json.loads(match.group(1))
        except ValueError:
            logger.warning(f"lafourche_fr: unparseable __NEXT_DATA__ at {response.url}")
            return [], None
        try:
            page_props = data["props"]["pageProps"]
            initial_results = page_props["searchServerState"]["initialResults"]
            index_key = next(iter(initial_results))
            result = initial_results[index_key]["results"][0]
        except (KeyError, IndexError, StopIteration, TypeError):
            logger.warning(f"lafourche_fr: unexpected payload shape at {response.url}")
            return [], None
        return result.get("hits", []), result.get("nbPages")

    def parse_page(self, response):
        page = response.meta["page"]
        hits, nb_pages = self._extract_hits(response)
        logger.info(f"lafourche_fr: page={page} hits={len(hits)} nb_pages={nb_pages}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for hit in hits:
            price = hit.get("price")
            if price is None:
                continue
            yield {
                "product_id": str(hit.get("sku") or hit.get("id")),
                "product_name": htmlmod.unescape(str(hit.get("title") or ""))[:500],
                "category": None,
                "price": str(price),
                "currency": self.currency,
                "available": bool(hit.get("inventory_available", True)),
                "url": f"{_BASE}/products/{hit.get('handle', '')}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if hits and page < MAX_PAGES and (nb_pages is None or page < nb_pages):
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/collections/all?page={nxt}",
                callback=self.parse_page,
                meta={"page": nxt},
            )
