"""Bissau Online Market (bissauonlinemarket.com) -- Guinea-Bissau classifieds.

A small WordPress/Elementor classifieds site for Bissau. WooCommerce assets are
present in the theme but the Store API route is absent (404 on
/wp-json/wc/store/v1/products) -- listings are a JetEngine custom post type, not
Woo products, so the catalogue is read from the core WP REST collection

    /wp-json/wp/v2/_classificados?per_page=100

which returns the whole catalogue in one page and needs no auth. That gives each
ad's canonical URL and title; the PRICE is not in the REST payload (it is a
JetEngine meta field the endpoint does not expose), so each ad's own page is
fetched and parsed.

Price-selector gotcha, verified 2026-09-12: every product page renders SEVEN
`.jet-listing-dynamic-field__content` price nodes -- its own, plus one per other
ad in the site-wide "related" grid that Elementor repeats on every page. Naively
selecting all of them would emit the entire catalogue once per page. The FIRST
such node is reliably the page's own price; this was checked against all 7 ads
and each first-node value matches its own item (iPhone 14 -> 950.000, PS5 ->
790.000, Compaq Presario -> 290.000, Drone Mijia -> 60.000, microphone ->
45.000, and the two website-build service ads -> 300.000 / 250.000).

Catalogue is genuinely small and static: 7 ads at onboarding, 5 goods plus 2
priced services. Prices are plain FCFA integers with a "." thousands separator
(950.000 FCFA = 950000 XOF); there is no minor unit in XOF.
"""

import re
from datetime import datetime, timezone

import scrapy

BASE = "https://bissauonlinemarket.com"
REST_URL = f"{BASE}/wp-json/wp/v2/_classificados?per_page=100"
_PRICE_RE = re.compile(r"([\d][\d\s.,]*)\s*FCFA")
_TAG_RE = re.compile(r"<[^>]+>")


class BissauOnlineMarketGwSpider(scrapy.Spider):
    name = "bissauonlinemarket_gw"
    allowed_domains = ["bissauonlinemarket.com"]
    currency = "XOF"
    language = "pt"
    source_label = "bissauonlinemarket_gw"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(REST_URL, callback=self.parse_index, dont_filter=True)

    def parse_index(self, response):
        try:
            ads = response.json()
        except ValueError:
            self.logger.warning("non-JSON REST response at %s", response.url)
            return
        if not isinstance(ads, list):
            return
        self.logger.info("%s catalogue size=%d", self.name, len(ads))
        for ad in ads:
            link = ad.get("link")
            if not link:
                continue
            yield scrapy.Request(
                link,
                callback=self.parse_ad,
                cb_kwargs={
                    "ad_id": str(ad.get("id")),
                    "title": self._clean(
                        (ad.get("title") or {}).get("rendered") or ""
                    ),
                },
            )

    def parse_ad(self, response, ad_id, title):
        # First price node only -- the rest belong to the site-wide related grid
        # that Elementor repeats on every page (see module docstring).
        nodes = response.css(".jet-listing-dynamic-field__content::text").getall()
        price = None
        for raw in nodes:
            m = _PRICE_RE.search(raw)
            if m:
                price = self._to_number(m.group(1))
                break
        if price is None or price <= 0:
            self.logger.warning("no price on %s", response.url)
            return

        name = title or self._clean(response.css("title::text").get() or "")
        if not name:
            return

        yield {
            "product_id": ad_id,
            "product_name": name[:500],
            "category": None,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _clean(raw: str) -> str:
        import html as _html

        return _html.unescape(_TAG_RE.sub("", raw)).strip()

    @staticmethod
    def _to_number(raw: str) -> float | None:
        """`950.000` / `1 250 000` -> 950000.0 / 1250000.0.

        XOF has no minor unit, so every separator here is a thousands
        separator -- do NOT treat a trailing `.000` as a decimal fraction.
        """
        s = re.sub(r"[^\d]", "", raw)
        try:
            return float(s) if s else None
        except ValueError:
            return None
