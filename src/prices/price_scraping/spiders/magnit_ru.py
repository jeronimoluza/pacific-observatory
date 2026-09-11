"""
Magnit (RU) — one of Russia's two largest grocery chains, magnit.ru.

Was filed dead in known_blockers (probed 2026-08-07): the sitemap index's
`__sitemap__/products.xml` child lists ~19,900 `/product/<slug>` URLs that
ALL 404 (soft-404, renders the homepage shell) — a stale/mismatched
sitemap, not a WAF block.

Re-probed 2026-09-11: `__sitemap__/products.xml` is the wrong child of the
sitemap index. `__sitemap__/catalog.xml` (a sibling child, same index) lists
real, live CATEGORY pages (`/catalog/<id>-<slug>`), and every category page
embeds a `<script id="offer-catalog-jsonld" type="application/ld+json">`
OfferCatalog block with ~30 real Offer entries (name, url, price,
priceCurrency=RUB) directly in the server-rendered HTML — no need to visit
individual PDPs at all. Confirmed live: "Крабовые палочки Vici..." 139.99
RUB. This is the sitemap-INDEX-vs-shard trap from the onboarding brief, one
level removed: the *right* shard was a sibling of the one already checked,
not a child of it.

Prices are for one specific delivery address/store (embedded in the page
copy, e.g. "Краснодарский край, Краснодар г...") — same caveat as any
single-location retailer scrape; no location parameter was found to vary
this from a single simple GET.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

CATALOG_SITEMAP = "https://magnit.ru/__sitemap__/catalog.xml"
OFFER_CATALOG_RE = re.compile(
    r'<script[^>]*id="offer-catalog-jsonld"[^>]*>(.*?)</script>', re.S
)


class MagnitRuSpider(scrapy.Spider):
    name = "magnit_ru"
    allowed_domains = ["magnit.ru"]
    currency = "RUB"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_ids: set[str] = set()

    async def start(self):
        yield scrapy.Request(
            CATALOG_SITEMAP, callback=self.parse_catalog_sitemap, errback=self.errback
        )

    def parse_catalog_sitemap(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        # Skip the bare /catalog root -- not a leaf category.
        cat_urls = [u for u in urls if u.rstrip("/") != "https://magnit.ru/catalog"]
        logger.info(f"catalog.xml: {len(urls)} urls, {len(cat_urls)} leaf categories")
        for u in cat_urls:
            yield scrapy.Request(u, callback=self.parse_category, errback=self.errback)

    def parse_category(self, response):
        m = OFFER_CATALOG_RE.search(response.text)
        if not m:
            return
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            logger.warning(f"bad offer-catalog-jsonld on {response.url}")
            return
        items = data.get("itemListElement") or []
        for offer in items:
            if not isinstance(offer, dict):
                continue
            url = offer.get("url") or ""
            price = offer.get("price")
            name = offer.get("name")
            if not price or not name or not url:
                continue
            pid_m = re.search(r"/product/(\d+)-", url)
            pid = pid_m.group(1) if pid_m else url
            if pid in self.seen_ids:
                continue
            self.seen_ids.add(pid)
            yield {
                "product_id": pid,
                "product_name": str(name).strip()[:500],
                "category": data.get("name"),
                "price": str(price),
                "currency": offer.get("priceCurrency") or self.currency,
                "available": offer.get("availability", "").endswith("InStock"),
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")
