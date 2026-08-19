"""
Spider for Khaji Kala (Iran) — https://khajikala.ir/.

Custom (non-WooCommerce) storefront selling building materials, plumbing,
electrical/lighting, kitchen fixtures, tools and hardware. Server-rendered
HTML — no JSON API found (Store API paths 404). URL discovery via
`/sitemap_categories.xml`, which lists every `/products/<slug>` category
page; each category paginates via `?PageNumber=N` (NOT `?page=N`, which
silently re-serves page 1 — confirmed live 2026-08-18: page 1 and page 2 of
kitchen-sinks returned disjoint product-id sets under PageNumber, identical
sets under page).

Each product page (`/product/<id>/<slug>`) carries a Schema.org Product
JSON-LD node with `offers.price` / `offers.priceCurrency` plus a sibling
BreadcrumbList node for category. Verified live: sink product 7392 ->
IRR 34,384,300, priceCurrency literally "IRR" (unlike the WooCommerce
cosmetics batch onboarded alongside this source, which quotes Toman under a
non-ISO "IRT" currency_code and needs x10 — khajikala's own JSON-LD is
already Rial-denominated, no conversion applied here).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SITEMAP_URL = "https://khajikala.ir/sitemap_categories.xml"
PRODUCT_URL_RE = re.compile(r"/product/(\d+)/[^\"'\s]+")
MAX_PAGES = 30


class KhajikalaIrSpider(scrapy.Spider):
    name = "khajikala_ir"
    allowed_domains = ["khajikala.ir"]
    currency = "IRR"
    language = "fa"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_products: set[str] = set()

    async def start(self):
        yield scrapy.Request(SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        cat_urls = [u for u in urls if "/products/" in u]
        logger.info(f"category sitemap: {len(cat_urls)} categories")
        for cu in cat_urls:
            yield scrapy.Request(
                cu,
                callback=self.parse_category,
                meta={"page": 1, "category_url": cu},
            )

    def parse_category(self, response):
        page = response.meta["page"]
        product_ids = set(PRODUCT_URL_RE.findall(response.text))
        new_ids = product_ids - self.seen_products
        for m in PRODUCT_URL_RE.finditer(response.text):
            pid = m.group(1)
            if pid in self.seen_products:
                continue
            self.seen_products.add(pid)
            yield scrapy.Request(
                response.urljoin(m.group(0)),
                callback=self.parse_product,
            )
        logger.info(
            f"{response.meta['category_url']} page={page} products={len(product_ids)} new={len(new_ids)}"
        )
        if new_ids and page < MAX_PAGES:
            nxt = page + 1
            sep = "&" if "?" in response.meta["category_url"] else "?"
            yield scrapy.Request(
                f"{response.meta['category_url']}{sep}PageNumber={nxt}",
                callback=self.parse_category,
                meta={"page": nxt, "category_url": response.meta["category_url"]},
            )

    def parse_product(self, response):
        product = self._extract_type(response, "Product")
        if not product:
            return
        offer = product.get("offers") or {}
        if isinstance(offer, list):
            offer = offer[0] if offer else {}
        price = offer.get("price")
        name = product.get("name")
        try:
            price_ok = price is not None and float(price) > 0
        except (TypeError, ValueError):
            price_ok = False
        if not (price_ok and name):
            return
        brand = product.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        yield {
            "product_id": str(product.get("sku") or response.url),
            "product_name": str(name).strip()[:500],
            "brand": brand,
            "category": self._extract_category(response),
            "price": str(price),
            "currency": offer.get("priceCurrency") or self.currency,
            "available": "InStock" in str(offer.get("availability") or ""),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _extract_type(response, type_name):
        for raw in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            candidates = (
                data.get("@graph")
                if isinstance(data, dict) and "@graph" in data
                else [data]
            )
            for c in candidates:
                if isinstance(c, dict) and c.get("@type") == type_name:
                    return c
        return None

    @classmethod
    def _extract_category(cls, response):
        crumbs_node = cls._extract_type(response, "BreadcrumbList")
        if not crumbs_node:
            return None
        crumbs = crumbs_node.get("itemListElement") or []
        names = [
            cr.get("name") for cr in crumbs if isinstance(cr, dict) and cr.get("name")
        ]
        return " > ".join(names) if names else None
