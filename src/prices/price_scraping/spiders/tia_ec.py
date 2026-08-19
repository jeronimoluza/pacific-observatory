"""
Spider for TIA (Ecuador) -- https://www.tia.com.ec/.

Grupo El Rosado general-merchandise + grocery chain, Magento 2 storefront.
The `/rest/V1/products` REST endpoint and `/graphql` both 401/403 without
an auth token, but every category listing page embeds the GA4 dataLayer
`ecommerce.items` payload as inline JSON (`item_name`, `item_id`,
`price`, `item_category`) alongside the server-rendered product grid --
this is a hydration-payload pass, cleaner than parsing the HTML grid
directly. 13 top-level nav categories (grocery is "supermercado";
the rest is general merchandise -- bebes, moda, electrodomesticos, etc --
crawled too per whole-catalog convention). Pagination is `?p=N`; Magento
renders a 5-page sliding window with a "next" link that disappears past
the last page.

Re-verified live 2026-08-06: GET /supermercado -> 200, 418KB, 12
item_name/price pairs per page e.g. 'ACEITE CON ACHIOTE ALESOL 200 ML'
USD 0.99. Currency USD matches countries.yaml (Ecuador is dollarized).
"""

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.tia.com.ec"
_CATEGORIES = [
    "supermercado",
    "bebes",
    "moda",
    "higiene-salud-y-belleza",
    "mascotas",
    "herramientas-y-ferreteria",
    "electrodomesticos",
    "tecnologia",
    "movilidad",
    "juguetes",
    "deportes",
    "playa",
    "escolar",
    "hogar",
]
MAX_PAGES_PER_CATEGORY = 100
_ITEM_RE = re.compile(
    r'\{"item_name":"(.*?)","affiliation":"[^"]*","item_id":"(\d+)",'
    r'"price":([0-9.]+),"item_category":"([^"]*)"'
)


class TiaEcSpider(scrapy.Spider):
    name = "tia_ec"
    allowed_domains = ["tia.com.ec"]
    currency = "USD"
    language = "es"

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
        for slug in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/{slug}",
                callback=self.parse_category,
                meta={"slug": slug, "page": 1},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        matches = _ITEM_RE.findall(response.text)
        for name, item_id, price, category in matches:
            name = json.loads(f'"{name}"').strip()
            category = json.loads(f'"{category}"').strip() if category else slug
            if not name or not price:
                continue
            yield {
                "product_id": item_id,
                "product_name": name,
                "category": category,
                "price": price,
                "currency": self.currency,
                "url": f"{_BASE}/catalog/product/view/id/{item_id}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        if matches and page < MAX_PAGES_PER_CATEGORY:
            next_href = response.css("li.pages-item-next a::attr(href)").get()
            if next_href:
                yield scrapy.Request(
                    urljoin(_BASE, next_href),
                    callback=self.parse_category,
                    meta={"slug": slug, "page": page + 1},
                )
