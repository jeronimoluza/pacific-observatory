"""
Picard (France, frozen-food specialist) — https://www.picard.fr/.

Salesforce Commerce Cloud (SFCC/Demandware) storefront — no WAF encountered,
plain curl_cffi clears the front page and every /rayons/ category page.

Every /rayons/... category page (any depth — top-level "aperitifs-et-entrees"
down to a leaf like "aperitifs-et-entrees/aperitifs/aperitifs-froids") embeds
one `data-gtm="{...}"` JSON blob per product tile alongside its
`data-pid="<id>"`, with item_name, the full 3-level category breadcrumb,
price, currency, and item_format (pack-size text) already flattened — no
PDP visit needed. Leaf pages render every product in the leaf (verified:
the sort-order dropdown's `Search-UpdateGrid?...&sz=N` always matches the
tile count, e.g. sz=19 for 19 tiles on aperitifs-froids); intermediate
pages show a smaller curated/teaser subset, which is fine — the same
products surface again on their own leaf page, and Scrapy's per-URL
request dedup plus DuplicationPipeline's url-based item dedup mean nothing
is lost or double-counted by crawling every category depth.

Rather than hardcode the category tree, a CrawlSpider follows every
/rayons/ link found on every /rayons/ page (breadth grows shallow: the
subcategory links stop once a page has no further /rayons/ children).

Product URL is reconstructed via the SFCC canonical Product-Show route
(pid is globally resolvable there without needing the PDP's slug).

Currency: EUR (matches countries.yaml and the page's own currency field).

Verified live 2026-09-06: aperitifs-froids leaf alone yielded 19 real SKUs,
e.g. "PAIN SURPRISE CAMPAGNE" EUR 19.99, "20 CANAPES APERITIFS 140G"
EUR 8.99.
"""

import html
import json
import logging
import re

import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

logger = logging.getLogger(__name__)

_TILE_RE = re.compile(r'data-pid="(\d+)"\s+data-gtm="([^"]+)"')


class PicardFrSpider(CrawlSpider):
    name = "picard_fr"
    allowed_domains = ["picard.fr"]
    start_urls = ["https://www.picard.fr/"]
    currency = "EUR"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEPTH_LIMIT": 6,
    }

    rules = (
        Rule(
            LinkExtractor(allow=r"/rayons/", deny=r"[?&]"),
            callback="parse_category",
            follow=True,
        ),
    )

    def parse_category(self, response):
        found = 0
        for pid, raw in _TILE_RE.findall(response.text):
            item = self._item(pid, raw)
            if item:
                found += 1
                yield item
        logger.info(f"{self.name}: {response.url} tiles_yielded={found}")

    def _item(self, pid, raw_gtm):
        try:
            d = json.loads(html.unescape(raw_gtm))
        except (json.JSONDecodeError, ValueError):
            return None
        name = d.get("item_name")
        price = d.get("price")
        if not name or price in (None, ""):
            return None
        try:
            if float(price) == 0:
                return None
        except (TypeError, ValueError):
            return None
        breadcrumb = " > ".join(
            str(d.get(k)) for k in ("item_category", "item_category2", "item_category3")
            if d.get(k)
        )
        details = d.get("item_format") or None
        return {
            "product_id": pid,
            "product_name": str(name).strip()[:500],
            "category": breadcrumb or None,
            "price": str(price),
            "currency": d.get("currency") or self.currency,
            "details": details,
            "available": d.get("item_availability") != "out_of_stock",
            "url": (
                "https://www.picard.fr/on/demandware.store/"
                f"Sites-picard-Site/fr_FR/Product-Show?pid={pid}"
            ),
            "language": self.language,
        }
