"""
S i D Komersial / sid-shop.com (Bulgaria) — https://www.sid-shop.com/.

Sofia-based online alcohol retailer (С и Д Комерсиал ООД — company name and
Sofia address read off the site's own Organization JSON-LD, so the country
attribution does not rest on the .com TLD). Wine, rakia, whisky, rum, brandy
and beer, i.e. COICOP 02.1 — a division Bulgaria's existing manifests
(ogimarket, tmarketonline, gracia_cosmetics, five eurostat fetchers) cover
only incidentally.

Tier 1A, Magento 2 (Stenik theme), server-rendered, no anti-bot.

URL discovery: Magento writes its sitemap to /media/sitemap.xml, NOT to
/sitemap.xml (which 404s here). robots.txt is what points at it. 9,543
product URLs as of 2026-09-05, all bare single-segment slugs.

TWO EXTRACTION NOTES:

1. The Product JSON-LD carries name, sku, mpn (an EAN) and offers, but NO
   `category` key. The category path is only in the rendered breadcrumb,
   which is marked up as schema.org BreadcrumbList microdata (itemprop=
   "name" inside `.breadcrumbs .items`) rather than as a JSON-LD node. The
   spider reads it from the DOM and drops the leading "Начало" (Home) crumb.
2. `offers` is a LIST here, not an object, and `price` is a float rather than
   a string. Both shapes have to be handled or every row is dropped.

CURRENCY: EUR, taken from the site's own offers.priceCurrency. Bulgaria
adopted the euro in January 2026; countries.yaml still defaults to BGN, and
the site-declared currency wins per the onboarding skill's currency rule —
the same trap already recorded on tmarketonline_bg and gracia_cosmetics_bg.

SPIDER PAGE FAMILY: PDP only (sitemap-driven; category grids never fetched).
"""

import json
import logging
from datetime import datetime, timezone

import scrapy
from scrapy.http import TextResponse

logger = logging.getLogger(__name__)

_SITEMAP = "https://www.sid-shop.com/media/sitemap.xml"


class SidShopBgSpider(scrapy.Spider):
    name = "sid_shop_bg"
    allowed_domains = ["sid-shop.com"]
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
        # Scope to <url>/<loc>: a bare //loc would also pick up any
        # <image:loc> children and queue image requests (the trap that cost
        # ebag_bg half its first run).
        urls = response.xpath(
            "//*[local-name()='url']/*[local-name()='loc']/text()"
        ).getall()
        # Magento's sitemap mixes 9,407 single-segment PRODUCT slugs with 136
        # multi-segment CATEGORY pages (/alkoholni-napitki/uiski/amerikansko)
        # and a few CMS pages. Categories carry no Product JSON-LD, so they are
        # pure waste -- and because Scrapy's default scheduler is LIFO they sit
        # at the FRONT of the crawl, which made the first test run spend its
        # whole budget on them before reaching a single product. Keep depth-1
        # paths only.
        urls = [
            u.strip()
            for u in urls
            if u.strip()
            and len(u.strip().rstrip("/").split("://", 1)[-1].split("/")) == 2
        ]
        logger.info(f"{self.name}: {len(urls)} product urls in sitemap")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        if not isinstance(response, TextResponse):
            return
        product = self._extract_product(response)
        if not product:
            logger.warning(f"{self.name}: no Product JSON-LD at {response.url}")
            return
        offers = product.get("offers")
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if not isinstance(offers, dict):
            offers = {}
        name = product.get("name")
        price = offers.get("price")
        if not name or price is None:
            return
        try:
            if float(price) <= 0:
                return
        except (TypeError, ValueError):
            return
        availability = str(offers.get("availability") or "")
        yield {
            "product_id": str(product.get("sku") or offers.get("sku") or response.url),
            "product_name": str(name).strip()[:500],
            "category": self._breadcrumb(response),
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": "instock" in availability.lower().replace("/", "")
            if availability
            else True,
            "url": response.url,
            "language": self.language,
            "barcode_gtin": str(product.get("mpn")) if product.get("mpn") else None,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _breadcrumb(response) -> str | None:
        names = [
            t.strip()
            for t in response.css(
                '.breadcrumbs .items [itemprop="name"]::text'
            ).getall()
        ]
        names = [n for n in names if n and n != "Начало"]
        return " > ".join(names) or None

    @staticmethod
    def _extract_product(response):
        for raw in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            nodes = data if isinstance(data, list) else [data]
            for node in nodes:
                if isinstance(node, dict) and node.get("@type") == "Product":
                    return node
        return None
