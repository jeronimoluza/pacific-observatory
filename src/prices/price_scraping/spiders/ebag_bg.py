"""
eBag.bg (Bulgaria) — https://www.ebag.bg/.

Bulgaria's largest home-delivery online supermarket. Tier 1A: PDPs are
server-rendered and carry a single schema.org Product JSON-LD node with
name, sku, a full ` > `-joined category path, and offers.price /
offers.priceCurrency. Nothing else on the page needs parsing.

URL discovery uses the site's own product sitemap. The sitemap INDEX at
/sitemap.xml lists both an English (`/en/sitemap_products_en.xml`) and a
Bulgarian (`/sitemap_products_bg.xml`) product sitemap over the same
catalogue; only the Bulgarian one is walked, because collecting both would
double-count every SKU under two URLs that the DuplicationPipeline (which
dedups on `url`) would happily keep. 21,107 Bulgarian product URLs as of
2026-09-05.

CURRENCY: EUR. Bulgaria adopted the euro in January 2026 and the storefront's
own `offers.priceCurrency` says EUR, so the site-declared currency wins over
the stale BGN default in countries.yaml — same trap as tmarketonline_bg,
gracia_cosmetics_bg and gladen_bg.

Assortment is wide: groceries and drinks dominate but the catalogue also
carries a full pharmacy/cosmetics wing ("Аптека > ..."), so `coicop_codes` is
deliberately unset and the classifier assigns leaves per product.

SPIDER PAGE FAMILY: PDP only (sitemap-driven; category grids are never
fetched).
"""

import json
import logging
from datetime import datetime, timezone

import scrapy
from scrapy.http import TextResponse

logger = logging.getLogger(__name__)

_SITEMAP = "https://www.ebag.bg/sitemap_products_bg.xml"


class EbagBgSpider(scrapy.Spider):
    name = "ebag_bg"
    allowed_domains = ["ebag.bg"]
    currency = "EUR"
    language = "bg"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        # `//loc` alone is WRONG on this sitemap: every <url> entry also carries
        # an <image:image><image:loc> child pointing at /products/images/<id>/800.
        # Matching all <loc> nodes therefore queues one image request per
        # product -- Scrapy hands those back as a bare Response whose .xpath
        # raises NotSupported, which is exactly half the requests in the first
        # test run (61 rows, 61 ERRORs). Scope to <url>/<loc>.
        urls = response.xpath(
            "//*[local-name()='url']/*[local-name()='loc']/text()"
        ).getall()
        logger.info(f"{self.name}: {len(urls)} product urls in sitemap")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        # A handful of sitemap entries resolve to a non-text body (Scrapy hands
        # those back as a bare Response, whose .xpath raises NotSupported and
        # kills the callback). Skip them rather than let one bad row abort the
        # crawl.
        if not isinstance(response, TextResponse):
            logger.warning(f"{self.name}: non-text response at {response.url}")
            return
        product = self._extract_product(response)
        if not product:
            logger.warning(f"{self.name}: no Product JSON-LD at {response.url}")
            return
        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        name = product.get("name")
        price = offers.get("price")
        if not name or price is None:
            return
        try:
            if float(price) <= 0:
                return
        except (TypeError, ValueError):
            return
        category = product.get("category")
        if isinstance(category, dict):
            category = category.get("name")
        availability = str(offers.get("availability") or "")
        yield {
            "product_id": str(
                product.get("sku") or response.url.rstrip("/").rsplit("/", 1)[-1]
            ),
            "product_name": str(name).strip()[:500],
            "category": str(category) if category else None,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": "instock" in availability.lower().replace("/", "")
            if availability
            else True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _extract_product(response):
        for raw in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            nodes = (
                data.get("@graph")
                if isinstance(data, dict) and "@graph" in data
                else [data]
            )
            if not isinstance(nodes, list):
                nodes = [nodes]
            for node in nodes:
                if isinstance(node, dict) and node.get("@type") == "Product":
                    return node
        return None
