"""
Kona Livr — named supermarket merchants only (Guinea).

konalivr_gn (already onboarded) crawls all 16 merchants behind the Kona
Livr delivery marketplace at https://www.konalivr.com/ — supermarkets,
pharmacies, bakeries, juice bars and restaurants blended into one
channel: marketplace source. Per the onboarding convention, a named
retailer chain sitting behind a delivery marketplace can also be
onboarded as its own first-party source ("a named supermarket behind a
delivery app is a supermarket").

This spider targets only the two Kona Livr merchant pages that are
recognisable supermarket chains — /merchants/carrefour-express-kaloum
(Carrefour Express, Kaloum) and /merchants/super-u-kipe (Super U,
Kipé) — and tags the result channel: supermarket. It does not re-crawl
the marketplace index or the other 14 merchants; those stay inside
konalivr_gn.

Verified live 2026-09-01: both merchant pages are server-rendered HTML,
same markup as konalivr_gn (div.mb-12 > h2 category + div.rounded-2xl
product cards, h3 name / span.font-bold.text-brand-600 price "XX XXX
GNF"). Each merchant returns exactly 4 products, real named grocery
SKUs with real GNF prices, e.g. Carrefour Express: "Pack 12 yaourts
nature" 13 000 GNF, "Beurre 250 g" 20 000 GNF, "Œufs (x30)" 22 000 GNF,
"Pâtes 500 g (x4)" 14 000 GNF; Super U: "Pack 6 eaux minérales 1,5 L"
15 000 GNF, "Pack bissap 6x500 ml" 15 000 GNF, "Riz parfumé 5 kg"
18 000 GNF, "Huile de tournesol 5 L" 15 000 GNF. 8 products total across
the two merchants (no overlap in SKUs). Same caveat as konalivr_gn: the
uniform 4-products-per-merchant pattern suggests a small/seed catalogue
rather than a fully live-managed inventory, but the products and prices
are real and GNF-denominated.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.konalivr.com"
MERCHANT_SLUGS = ["carrefour-express-kaloum", "super-u-kipe"]

_PRICE_RE = re.compile(r"([\d\s.,]+)\s*GNF")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text):
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class KonalivrSupermarketGnSpider(scrapy.Spider):
    name = "konalivr_supermarket_gn"
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
        for slug in MERCHANT_SLUGS:
            yield scrapy.Request(
                f"{BASE_URL}/merchants/{slug}",
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
