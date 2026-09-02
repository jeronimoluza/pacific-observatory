"""
Kona Livr (Guinea) — https://www.konalivr.com/.

Multi-vendor delivery marketplace for Conakry. The homepage lists 16
merchants (supermarkets, pharmacies, bakeries, juice bars, restaurants)
via plain <a href="/merchants/<slug>"> links; the candidate note's "app
promos" landing figures were delivery fees, not item prices.

Each merchant page is server-rendered HTML with real product cards,
grouped under category headers (e.g. "Frais", "Épicerie", "Médicaments",
"Matériel"): div.mb-12 > h2 (category) + div.rounded-2xl per product,
each with h3 (name), span.font-bold.text-brand-600 (price, "XX XXX
GNF") and a p (short description). No product id in the markup, so
product_id is synthesised from the merchant slug + slugified name.

Catalog is small and fixed: 16 merchants x 4 items = 64 products total
(verified 2026-08-31, every merchant returns exactly 4). No stock/
availability signal on the page — all treated as available.

SPLIT 2026-09-01: two of the 16 merchants — carrefour-express-kaloum
(Carrefour Express) and super-u-kipe (Super U) — are named supermarket
chains and were carved out into their own source, konalivr_supermarket_gn
(channel: supermarket), per the "named supermarket behind a delivery app
is a supermarket" convention. This spider EXCLUDES those two slugs so
the two sources never emit the same shelf twice. Do not re-add them here
and do not re-merge the two sources — konalivr_supermarket_gn owns them.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.konalivr.com"

# Owned by konalivr_supermarket_gn (channel: supermarket) — see module
# docstring. Excluded here to avoid double-counting the same shelf.
_EXCLUDED_MERCHANTS = {"carrefour-express-kaloum", "super-u-kipe"}

_PRICE_RE = re.compile(r"([\d\s.,]+)\s*GNF")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text):
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class KonalivrGnSpider(scrapy.Spider):
    name = "konalivr_gn"
    allowed_domains = ["konalivr.com"]
    currency = "GNF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(BASE_URL, callback=self.parse_index, errback=self.errback)

    def parse_index(self, response):
        hrefs = sorted(set(response.css('a[href^="/merchants/"]::attr(href)').getall()))
        logger.info(f"{self.name}: merchants found={len(hrefs)}")
        for href in hrefs:
            slug = href.rstrip("/").rsplit("/", 1)[-1]
            if slug in _EXCLUDED_MERCHANTS:
                logger.info(
                    f"{self.name}: skipping {slug} (owned by konalivr_supermarket_gn)"
                )
                continue
            yield response.follow(
                href,
                callback=self.parse_merchant,
                errback=self.errback,
                meta={"merchant": slug},
            )

    def parse_merchant(self, response):
        merchant = response.meta["merchant"]
        found = 0
        for section in response.css("div.mb-12"):
            category = (section.css("h2::text").get() or "").strip()
            for card in section.css("div.rounded-2xl"):
                name = (card.css("h3::text").get() or "").strip()
                raw_price = (
                    card.css("span.font-bold.text-brand-600::text").get() or ""
                ).strip()
                if not name or not raw_price:
                    continue
                match = _PRICE_RE.search(raw_price)
                if not match:
                    continue
                amount = (
                    match.group(1).replace(" ", "").replace("\xa0", "").replace(",", "")
                )
                if not amount or float(amount) == 0:
                    continue

                found += 1
                product_id = f"{merchant}-{_slugify(name)}"
                yield {
                    "product_id": product_id,
                    "product_name": name[:500],
                    "category": f"{merchant}:{category}" if category else merchant,
                    "price": amount,
                    "currency": self.currency,
                    "available": True,
                    # All products on a merchant page share the same URL;
                    # append a fragment so the pipeline's url-based dedup
                    # does not collapse every merchant down to one row.
                    "url": f"{response.url}#{product_id}",
                    "language": self.language,
                    "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                }
        logger.info(f"{self.name}: {response.url} merchant={merchant} yielded={found}")

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
