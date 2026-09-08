"""
Spider for John Bull (The Bahamas) -- https://www.johnbull.com/

Luxury department retailer (official Rolex/Tudor/Cartier/Bvlgari/Gucci
retailer in Nassau). Candidate GOTCHA flagged this as "not production-
approved until live status, public price access ... verified" -- checked
every non-Rolex category page (jewelry, beauty-fragrance, time-pieces,
tudor-watches, panerai-watches, bvlgari, cartier, gucci, chopard,
iwc-schaffhausen, breitling, jaeger-lecoultre, leather-accessories) and
NONE of them render a price in the raw HTML -- classic luxury-retail
"contact us for pricing". Only the Rolex sub-site (built on the
"Rolex-V7" WordPress plugin, a template shared by many authorized Rolex
dealers worldwide) renders real USD prices server-side, e.g.
/rolex/watches -> $64,900 in plain HTML. Tier 1A, no JS needed.

Verified live 2026-09-06 with curl_cffi impersonate=chrome124. Each Rolex
model page (submariner, datejust, etc.) repeats the same markup shape
across two container classes -- `rolexv7-product-slider-item` (used on the
/rolex/watches overview) and `rolex-collection-item` (used on individual
model pages) -- both wrapping: h5.rolex-legend16bold (brand, always
"Rolex"), p.rolex-body24bold (model name, e.g. "Datejust 41"), and one or
more p.rolex-legend16light text nodes where the LAST one holding a "$" is
the price (the ones before it are material/size description, e.g. "Oyster,
41 mm, Oystersteel and white gold").

start_urls is a fixed list of the Rolex model-family pages (there is no
crawlable "all models" index -- /rolex/watches only slides 8 highlighted
watches) enumerated from that overview page's own internal links.

coicop_classification: source_curated -- the ENTIRE scraped surface is
Rolex watches, so this is narrow (13.2.1.1 "Purchase of jewellery and
watches", confirmed against the repo's own COICOP xlsx via
prices.enrich.coicop_taxonomy). channel: dept-store -- John Bull itself is
a broad multi-category luxury retailer even though this pass only
harvests its one priced vertical.
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.johnbull.com"
_MODEL_SLUGS = [
    "watches",
    "new-watches",
    "1908",
    "air-king",
    "cosmograph-daytona",
    "datejust",
    "day-date",
    "deepsea",
    "explorer",
    "explorer-ii",
    "gmt-master-ii",
    "lady-datejust",
    "land-dweller",
    "oyster-perpetual",
    "sea-dweller",
    "sky-dweller",
    "submariner",
    "yacht-master",
    "yacht-master-ii",
]
_ID_RE = re.compile(r"/rolex/([a-z0-9-]+-m\d[\w-]*)$", re.I)


class JohnbullBsSpider(scrapy.Spider):
    name = "johnbull_bs"
    allowed_domains = ["johnbull.com"]
    currency = "USD"
    language = "en"

    start_urls = [f"{_BASE}/rolex/{slug}" for slug in _MODEL_SLUGS]

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def parse(self, response):
        cards = response.css(
            'a[class*="collection-item"], a[class*="product-slider-item"]'
        )
        for card in cards:
            brand = (card.css("h5.rolex-legend16bold::text").get() or "").strip()
            model = (card.css("p.rolex-body24bold::text").get() or "").strip()
            lights = [
                t.strip() for t in card.css("p.rolex-legend16light::text").getall()
            ]
            href = card.css("::attr(href)").get()
            if not (model and href and lights):
                continue
            price_text = lights[-1]
            if "$" not in price_text:
                continue
            product_name = f"{brand} {model}".strip()
            m = _ID_RE.search(href)
            product_id = m.group(1) if m else href

            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price_text,
                "currency": self.currency,
                "category": "Rolex Watches",
                "url": response.urljoin(href),
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
        logger.info(f"johnbull_bs: {response.url} -> {len(cards)} cards")
