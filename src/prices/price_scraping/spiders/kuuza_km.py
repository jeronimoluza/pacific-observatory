"""
Kuuza Comores (Comoros) — https://kuuzacomores.com/.

"La première MarketPlace des Comores" — a Laravel storefront selling for
several Comorian vendors (Kinaza, La Maison du Romarin, Wutamu, Ridaah,
Uzuri, plus imported appliance/electronics brands).

Why this matters for Comoros specifically: the country's only prior
manifest, `comoresenligne_km`, prices every product in **EUR** because it
sells to the diaspora — flagged there as an UNRATIFIED definitional call
that would zero the country if rejected. Kuuza prices in **KMF**, the
currency `countries.yaml` lists for Comoros, so it is the first
domestic-currency price source the country has.

Feasibility (probed 2026-09-05):
  * No WAF. `curl_cffi impersonate=chrome124` returns 200 on the homepage,
    on every sitemap, on category pages and on PDPs.
  * `/sitemap.xml` is a sitemap INDEX. The product shards are
    `products-YYYY-MM.xml`, one per month the catalogue grew; walking all
    19 of them gives **361 product URLs** site-wide (measured). That is the
    authoritative expected row count for this source — a run that returns
    materially fewer has lost pages somewhere.
  * Every PDP server-renders three `application/ld+json` blocks: WebSite,
    BreadcrumbList, and a schema.org **Product** carrying name, sku,
    category, description, image and an Offer with `price` +
    `priceCurrency: "KMF"` + availability. This is Tier 1A — plain HTML,
    no JS, no API, no Playwright.

Samples verified live:
    Cumin Moulu 80g            1,200 KMF   (category "Epices des Comores")
    Romarin Séché 100g         3,800 KMF   (category "Maison du Romarin")
    Congélateur 198 L Berklays 210,000 KMF (category "Congélateurs")

SCOPE: the whole catalogue, deliberately UNSCOPED — same call as
`comoresenligne_km`. Kuuza is not food-led: of its 75 product categories
the food/spice ones (`epices-des-comores`, `maison-du-romarin`, and the
edible part of `koli-ya-komori`) hold on the order of 15-20 SKUs, while
appliances, home textiles, cosmetics and hi-tech make up the bulk. Non-food
rows are wanted too and the classifier assigns leaves per product, so no
category filter is applied.

`price` is a plain decimal string in MAJOR units (KMF has no minor unit in
practice) — 1200 / 3800 / 210000 all check against the rendered page. No
minor-unit divide.

Page family parsed: **PDP** (product detail pages, reached from sitemap
shards; the spider never parses a listing page).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://kuuzacomores.com"
SITEMAP_INDEX = f"{BASE_URL}/sitemap.xml"

_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S)
_LDJSON_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S
)


class KuuzaKmSpider(scrapy.Spider):
    name = "kuuza_km"
    allowed_domains = ["kuuzacomores.com"]
    currency = "KMF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.4,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            SITEMAP_INDEX, callback=self.parse_index, errback=self.errback
        )

    def errback(self, failure):
        logger.warning(f"{self.name}: request failed -- {failure.value!r}")

    def parse_index(self, response):
        shards = [
            u for u in _LOC_RE.findall(response.text) if "/products-" in u
        ]
        logger.info(f"{self.name}: {len(shards)} product sitemap shards")
        for u in shards:
            yield scrapy.Request(u, callback=self.parse_shard, errback=self.errback)

    def parse_shard(self, response):
        urls = [u for u in _LOC_RE.findall(response.text) if "/products/" in u]
        logger.info(f"{self.name}: {response.url} -> {len(urls)} product urls")
        for u in urls:
            yield scrapy.Request(u, callback=self.parse_pdp, errback=self.errback)

    def parse_pdp(self, response):
        product = None
        for block in _LDJSON_RE.findall(response.text):
            try:
                data = json.loads(block.strip())
            except (ValueError, json.JSONDecodeError):
                continue
            if isinstance(data, list):
                data = next(
                    (d for d in data if isinstance(d, dict) and d.get("@type") == "Product"),
                    None,
                )
            if isinstance(data, dict) and data.get("@type") == "Product":
                product = data
                break

        if product is None:
            logger.warning(f"{self.name}: no Product JSON-LD at {response.url}")
            return

        offer = product.get("offers") or {}
        if isinstance(offer, list):
            offer = offer[0] if offer else {}

        price = offer.get("price")
        name = (product.get("name") or "").strip()
        if price is None or not name:
            logger.warning(f"{self.name}: missing name/price at {response.url}")
            return
        try:
            if float(price) <= 0:
                return
        except (TypeError, ValueError):
            return

        availability = str(offer.get("availability") or "")

        yield {
            "product_id": product.get("sku") or response.url.rsplit("/", 1)[-1],
            "product_name": name[:500],
            "category": product.get("category") or "",
            "price": str(price),
            "currency": offer.get("priceCurrency") or self.currency,
            "available": "InStock" in availability or not availability,
            "url": product.get("url") or response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
