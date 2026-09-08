"""METRO Cash & Carry Russia -- https://online.metro-cc.ru/.

The Russia inventory recorded metro-cc.ru as "reachable, JSON-LD present but
missing `price` (lives only in a minified Nuxt blob)" and parked it. That is
true of the CORPORATE site (`www.metro-cc.ru`); the transactional store is a
different host, `online.metro-cc.ru`, and it server-renders a real product
grid -- no Playwright, no JSON blob parsing, no TLS impersonation
(``curl_cffi``-free plain Scrapy requests are enough; the site answers 200 to
a stock browser UA).

Two traps found while probing, both of which would silently produce a
worthless spider:

1. **Department pages are carousels, not listings.** ``/category/bakaleya``
   renders 0 grid products and ~16 slider cards
   (``catalog-1-level-product-card``). Only the deeper leaf pages
   (``/category/bakaleya/konservy``) carry the real grid, whose cards are
   ``catalog-2-level-product-card``. This spider extracts ONLY 2-level cards,
   so a mid-level page contributes navigation links and nothing else --
   exactly the homepage-carousel false positive the onboarding skill warns
   about.
2. **Two price magnitudes per card.** The rouble part and the kopeck part are
   separate spans (``product-price__sum-rubles`` = "189",
   ``product-price__sum-penny`` = ".91"); reading only the first gives a
   silently wrong price. Both are joined here. The price taken is the
   ``product-unit-prices__actual`` figure scoped INSIDE the card (the page
   also carries slider-card prices), which is the per-piece ("/шт") online
   price.

Enumerability verified: ``/category/bakaleya/konservy`` page 1 and page 2
return 30 SKUs each with ZERO overlap, and the paginator renders explicit
``?page=N`` links up to the last page (22 for that leaf), so the walk is
bounded by the site's own markup rather than by a guess.

METRO is cash-and-carry, so ``channel: wholesale``. Prices are the
unauthenticated default store's (Moscow) -- METRO prices by store and no
store cookie is set here, matching the single-city convention used by the
Ukrainian and Russian grocery sources in this repo.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://online.metro-cc.ru"
_CAT_RE = re.compile(r"^/category/[a-z0-9\-]+(?:/[a-z0-9\-]+)*$")


class MetroCcRuSpider(scrapy.Spider):
    name = "metro_cc_ru"
    allowed_domains = ["online.metro-cc.ru"]
    currency = "RUB"
    language = "ru"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.8,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru,en;q=0.8",
        },
    }

    async def start(self):
        yield scrapy.Request(_BASE + "/", callback=self.parse, errback=self.errback)

    # ------------------------------------------------------------------
    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        cat_path = self._category_from_url(response.url)

        cards = response.css("div.catalog-2-level-product-card")
        for card in cards:
            item = self._item(card, cat_path, scraped_at)
            if item:
                yield item
        if cards:
            logger.info("%s: %d products at %s", self.name, len(cards), response.url)

        # Follow deeper category pages and the paginator. Scrapy's dupefilter
        # collapses the heavy repetition in the mega-menu.
        for href in response.css("a::attr(href)").getall():
            if not href:
                continue
            path = urlparse(href).path
            query = urlparse(href).query
            if not path.startswith("/category/"):
                continue
            if query and not query.startswith("page="):
                continue
            if not _CAT_RE.match(path):
                continue
            yield response.follow(href, callback=self.parse, errback=self.errback)

    # ------------------------------------------------------------------
    def _item(self, card, cat_path, scraped_at):
        sku = card.attrib.get("data-sku")
        name = card.css("a.product-card-photo__link::attr(title)").get()
        if not name:
            name = card.css("span.product-card-name__text::text").get()
        if not name:
            return None
        name = name.strip()

        rub = card.css(
            ".product-unit-prices__actual .product-price__sum-rubles::text"
        ).get()
        if not rub:
            return None
        penny = (
            card.css(".product-unit-prices__actual .product-price__sum-penny::text")
            .get("")
            .strip()
        )
        raw = rub.strip().replace("\xa0", "").replace(" ", "") + penny
        try:
            amount = float(raw.replace(",", "."))
        except ValueError:
            logger.warning("%s: unparsable price %r for sku %s", self.name, raw, sku)
            return None
        if amount <= 0:
            return None

        href = card.css("a.product-card-photo__link::attr(href)").get()
        return {
            "product_id": sku,
            "product_name": name,
            "category": cat_path,
            "price": f"{amount:.2f}",
            "currency": self.currency,
            "available": True,
            "url": urljoin(_BASE, href) if href else _BASE + "/",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    @staticmethod
    def _category_from_url(url):
        path = urlparse(url).path
        if not path.startswith("/category/"):
            return None
        parts = [p for p in path[len("/category/") :].split("/") if p]
        return " > ".join(parts) if parts else None

    def errback(self, failure):
        logger.error(
            "%s: request failed %s — %r", self.name, failure.request.url, failure.value
        )
