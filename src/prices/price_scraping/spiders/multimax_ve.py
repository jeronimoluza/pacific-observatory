"""
Spider for multimax.com.ve -- Multimax, Venezuelan appliance/electronics/
home-goods retailer.

Custom Astro storefront (no VTEX/Shopify/WooCommerce/Magento fingerprint).
Category listing pages render inline products but with no visible
pagination control, so this spider walks the product sitemap directly
instead -- `sitemap.xml` -> `sitemap-productos.xml` lists 3,605 distinct
`/producto/<slug>` URLs (verified live 2026-09-01), a real catalog, not a
homepage carousel.

Each PDP embeds a schema.org `@graph` JSON-LD block server-side with a
`Product` node (name, sku, offers.price, offers.priceCurrency) and a
sibling `BreadcrumbList` node. Verified live: "Batidora Classic 4.25
litros KitchenAid" -> USD 480.99, sku K45SSOB, breadcrumb Electrodomesticos
> Batidoras. Currency is USD site-wide -- no VES or "tasa BCV" mention
found anywhere on a sampled PDP; this is a dollarized-retail storefront
like mafabre_ve / paotrolado_ve, not a BCV-derived-VES one like
farmatodo_ve / locatel_ve.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://www.multimax.com.ve/sitemap-productos.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)


class MultimaxVeSpider(scrapy.Spider):
    name = "multimax_ve"
    allowed_domains = ["multimax.com.ve"]
    currency = "USD"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "DOWNLOAD_DELAY": 0.2,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 4,
    }
    IMPERSONATE_PROFILE = "chrome124"

    async def start(self):
        yield scrapy.Request(
            _SITEMAP_URL,
            callback=self.parse_sitemap,
            meta={"impersonate": self.IMPERSONATE_PROFILE},
        )

    def parse_sitemap(self, response):
        urls = sorted(set(_LOC_RE.findall(response.text)))
        logger.info(f"multimax_ve: {len(urls)} product URLs in sitemap")
        for url in urls:
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_product(self, response):
        graph_nodes = []
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            if isinstance(data, dict) and isinstance(data.get("@graph"), list):
                graph_nodes.extend(data["@graph"])
            elif isinstance(data, dict):
                graph_nodes.append(data)

        product = next((n for n in graph_nodes if n.get("@type") == "Product"), None)
        if not product:
            return

        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        name = product.get("name")
        if not name or price in (None, "", 0, "0"):
            return

        breadcrumb = next(
            (n for n in graph_nodes if n.get("@type") == "BreadcrumbList"), None
        )
        category = None
        if breadcrumb:
            items = sorted(
                breadcrumb.get("itemListElement") or [],
                key=lambda x: x.get("position", 0),
            )
            names = [
                it.get("name")
                for it in items
                if it.get("name") and it.get("name") != "Inicio"
            ]
            if names and names[-1] == product.get("name"):
                names = names[:-1]
            if names:
                category = " > ".join(names)

        yield {
            "product_id": product.get("sku")
            or response.url.rstrip("/").rsplit("/", 1)[-1],
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": str(offers.get("availability", "")).endswith("InStock"),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _loads(block):
        try:
            return json.loads(block)
        except (ValueError, TypeError):
            return None
