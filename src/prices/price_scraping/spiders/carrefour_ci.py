"""
Carrefour Côte d'Ivoire — https://carrefour.ci/.

WordPress + Elementor corporate site (not a WooCommerce/PrestaShop
storefront — carrefour.ci/wp-json/wc/store/v1/products 404s). There is no
product catalog: the only priced items are on the /promotions/ archive, a
small rotating flyer of current in-store offers rendered as individual
Elementor pages (one page per promo item), paginated with WordPress's
default /promotions/page/N/.

Each promo detail page carries exactly two "<price> FCFA" strings (the
discounted price first, the crossed-out regular price second — confirmed by
comparing 3 sampled pages) and a numeric WordPress post id embedded in the
inline `elementorFrontendConfig` JS blob as "post":{"id":<id>,...}. The
lower of the two prices is emitted (what a shopper actually pays).

Small, real catalog: 13 promo items measured live 2026-08-31 across 2 pages
(11 on /promotions/, 2 on /promotions/page/2/; page/3/ 404s). This is
Carrefour CI's only public price signal — the rest of carrefour.ci is
corporate/HR content.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://carrefour.ci"
_PRICE_RE = re.compile(r"([\d\s]+)\s*FCFA")
_POST_ID_RE = re.compile(r'"post":\{"id":(\d+)')
_TITLE_RE = re.compile(
    r'<h1 class="elementor-heading-title elementor-size-default">([^<]+)</h1>'
)


class CarrefourCiSpider(scrapy.Spider):
    name = "carrefour_ci"
    allowed_domains = ["carrefour.ci"]
    currency = "XOF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{BASE_URL}/promotions/",
            callback=self.parse_listing,
            errback=self.errback,
            meta={"page": 1},
        )

    def parse_listing(self, response):
        links = sorted(
            set(response.css('a[href*="/promotions/"]::attr(href)').getall())
        )
        product_links = [
            href
            for href in links
            if re.match(rf"^{BASE_URL}/promotions/[a-z0-9\-]+/?$", href)
        ]
        logger.info(
            f"{self.name}: page={response.meta['page']} promo links={len(product_links)}"
        )
        for href in product_links:
            yield response.follow(href, callback=self.parse_promo, errback=self.errback)

        # WordPress default pagination; the listing has no visible "next"
        # link so pages are walked as a counter until one 404s.
        next_page = response.meta["page"] + 1
        yield scrapy.Request(
            f"{BASE_URL}/promotions/page/{next_page}/",
            callback=self.parse_listing,
            errback=self.errback,
            meta={"page": next_page},
            dont_filter=True,
        )

    def parse_promo(self, response):
        title_match = _TITLE_RE.search(response.text)
        pid_match = _POST_ID_RE.search(response.text)
        prices = [
            int(p.replace(" ", "").replace(" ", ""))
            for p in _PRICE_RE.findall(response.text)
        ]
        if not title_match or not pid_match or not prices:
            logger.warning(f"{self.name}: could not parse {response.url}")
            return

        yield {
            "product_id": pid_match.group(1),
            "product_name": html.unescape(title_match.group(1)).strip()[:500],
            "category": "promotions",
            "price": str(min(prices)),
            "currency": self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        # A 404 on /promotions/page/N/ is the expected end-of-pagination signal.
        if failure.value and getattr(failure.value, "response", None) is not None:
            if failure.value.response.status == 404:
                return
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
