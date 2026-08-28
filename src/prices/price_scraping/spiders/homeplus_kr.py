"""
Spider for Homeplus (South Korea) — https://mfront.homeplus.co.kr, the mobile
front-end (m.homeplus.co.kr redirects here).

No JSON API sniff needed: the mobile front is server-rendered and each PDP
(`/item?itemNo=<id>&storeType=<HYPER|EXP>`) embeds a Schema.org Product
JSON-LD block with name/price/priceCurrency/mpn — plain curl, no Playwright.

`/list?categoryDepth=...&categoryId=...` category pages are a client-side
shell (no products in SSR HTML), so item discovery instead walks the site's
own sitemap.xml, which lists direct item URLs under a handful of buckets:
best-mart.xml / best-ssm.xml (bestsellers per store format) and
fixedPrice.xml (fixed-price promo items). `storeType=HYPER` is the large
hypermarket format; `storeType=EXP` ("SSM"/Express) is the small-format
convenience-adjacent store — same catalog platform, different assortment
and sometimes different price for the same SKU, so both are walked.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SITEMAPS = [
    "https://mfront.homeplus.co.kr/sitemap/best-mart.xml",
    "https://mfront.homeplus.co.kr/sitemap/best-ssm.xml",
    "https://mfront.homeplus.co.kr/sitemap/fixedPrice.xml",
]

LOC_RE = re.compile(r"<loc>([^<]+)</loc>")


class HomeplusKrSpider(scrapy.Spider):
    name = "homeplus_kr"
    allowed_domains = ["mfront.homeplus.co.kr"]
    currency = "KRW"
    language = "ko"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "RETRY_TIMES": 3,
    }

    def start_requests(self):
        for sitemap_url in SITEMAPS:
            yield scrapy.Request(sitemap_url, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = LOC_RE.findall(response.text)
        urls = [u.replace("&amp;", "&") for u in urls]
        logger.info(f"homeplus_kr: {len(urls)} item URLs in {response.url}")
        for url in urls:
            if "/item?itemNo=" not in url:
                continue
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product = self._extract_product(response)
        if not product:
            logger.warning(f"no Product JSON-LD found at {response.url}")
            return
        offer = product.get("offers") or {}
        if isinstance(offer, list):
            offer = offer[0] if offer else {}
        price = offer.get("price")
        name = product.get("name")
        if not (price and name):
            return
        category = self._extract_breadcrumb(response)
        yield {
            "product_id": str(product.get("mpn") or response.url),
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": offer.get("priceCurrency") or self.currency,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _extract_product(response):
        decoder = json.JSONDecoder()
        for raw in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            text = raw.lstrip()
            try:
                obj, _ = decoder.raw_decode(text)
            except json.JSONDecodeError:
                continue
            candidates = (
                obj.get("@graph")
                if isinstance(obj, dict) and "@graph" in obj
                else [obj]
            )
            for c in candidates:
                if isinstance(c, dict) and c.get("@type") == "Product":
                    return c
        return None

    @staticmethod
    def _extract_breadcrumb(response):
        decoder = json.JSONDecoder()
        for raw in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            text = raw.lstrip()
            try:
                obj, _ = decoder.raw_decode(text)
            except json.JSONDecodeError:
                continue
            candidates = (
                obj.get("@graph")
                if isinstance(obj, dict) and "@graph" in obj
                else [obj]
            )
            for c in candidates:
                if isinstance(c, dict) and c.get("@type") == "BreadcrumbList":
                    items = c.get("itemListElement") or []
                    names = [
                        (i.get("item") or {}).get("name")
                        for i in items
                        if isinstance(i.get("item"), dict)
                    ]
                    names = [n for n in names if n]
                    if names:
                        return " > ".join(names)
        return None
