"""vega.am — Armenia electronics/appliances hypermarket (OpenCart-based).

Verified live 2026-08-17. This is a genuine OpenCart storefront (theme
"chameleon", ``index.php?route=...`` AJAX calls visible in the page JS) but
its product-card markup (``div.product-name`` for the title, a
``div.price[data-price-value]``/``[data-special-value]`` attribute pair for
price) does not match either selector set in the shared
``OpencartBaseSpider`` (``_opencart_base.py``, tuned for the "Journal"-family
theme), so this is a standalone spider rather than a subclass — editing the
shared base to add a third theme's selectors would risk the other spiders
built on it.

``https://vega.am/sitemap.xml`` -> ``sitemap-categories.xml`` gives the full
category-URL tree (673 clean-SEO paths, e.g.
``/home-appliances/audio-video-and-photo/tv``); this spider keeps only leaf
paths (those that are not a path-prefix of a longer one) so parent
categories aren't walked twice. Each leaf accepts ``?page=<N>`` pagination
(verified). Price is read from the numeric ``data-price-value`` /
``data-special-value`` attributes on ``div.price`` rather than parsed from
text — ``data-special-value`` (the discounted/current price actually shown)
wins when present. ``product_id`` comes from the numeric id embedded in the
card's ``wishlist.add('<id>')`` onclick handler, NOT the URL: clean-SEO
product slugs often end in ``-<small-int>.html`` where the trailing int is a
colour/size *variant* index rather than a product id (verified collision:
many distinct sofas on ``/furniture-interior/living-room-furniture/sofas``
all end in ``-3.html``/``-4.html``/etc, which collapsed 121 rows down to 48
distinct ids before this fix).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_MAX_PAGES_PER_CATEGORY = 5


class VegaAmSpider(scrapy.Spider):
    name = "vega_am"
    allowed_domains = ["vega.am"]
    currency = "AMD"
    language = "hy"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.4,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            "https://vega.am/sitemap-categories.xml", callback=self.parse_sitemap
        )

    def parse_sitemap(self, response):
        locs = _LOC_RE.findall(response.text)
        paths = sorted(
            {
                loc.replace("https://vega.am", "")
                for loc in locs
                if loc != "https://vega.am"
            }
        )
        leaves = [
            p for p in paths if not any(o != p and o.startswith(p + "/") for o in paths)
        ]
        logger.info("vega_am: %d categories, %d leaves", len(paths), len(leaves))
        for path in leaves:
            yield scrapy.Request(
                f"https://vega.am{path}",
                callback=self.parse_category,
                meta={"page": 1, "path": path},
            )

    def parse_category(self, response):
        cards = response.css("div.product-thumb")
        scraped_at = datetime.now(timezone.utc).isoformat()
        category = (response.css("h1::text").get() or "").strip() or None
        emitted = 0
        for card in cards:
            item = self._parse_card(card, response, category, scraped_at)
            if item is not None:
                yield item
                emitted += 1

        page = response.meta["page"]
        path = response.meta["path"]
        logger.info(
            "vega_am: path=%s page=%s cards=%d items=%d",
            path,
            page,
            len(cards),
            emitted,
        )

        if cards and page < _MAX_PAGES_PER_CATEGORY:
            nxt = page + 1
            yield scrapy.Request(
                f"https://vega.am{path.rstrip('/')}/?page={nxt}",
                callback=self.parse_category,
                meta={"page": nxt, "path": path},
            )

    def _parse_card(self, card, response, category, scraped_at: str) -> dict | None:
        a = card.css("div.product-name a")
        href = a.attrib.get("href")
        title = a.css("::text").get()
        if not href or not title or not title.strip():
            return None
        title = title.strip()

        price_div = card.css("div.price")
        special = price_div.attrib.get("data-special-value")
        base = price_div.attrib.get("data-price-value")
        price_raw = special or base
        if not price_raw:
            return None
        try:
            float(price_raw)
        except ValueError:
            return None

        product_id = self._product_id(card, href)

        return {
            "product_id": product_id,
            "product_name": title[:500],
            "category": category,
            "price": price_raw,
            "currency": self.currency,
            "available": bool(card.css(".stock-status.instock")),
            "url": urljoin(response.url, href),
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    @staticmethod
    def _product_id(card, url: str) -> str:
        # The real numeric product id lives in the wishlist/compare/cart
        # button's onclick handler (e.g. wishlist.add('315781')), not in the
        # URL: clean-SEO product slugs often end in "-<small-int>.html" where
        # the trailing int is a colour/size *variant* index, not a product
        # id -- multiple distinct sofas can all end in "-3.html".
        onclick = card.css('[onclick*="wishlist.add"]::attr(onclick)').get()
        if onclick:
            m = re.search(r"wishlist\.add\('(\d+)'\)", onclick)
            if m:
                return m.group(1)
        return url.rstrip("/").rsplit("/", 1)[-1]
