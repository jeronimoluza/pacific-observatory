"""
Spider for Top! Veikali (Latvia) — https://www.toppartika.lv/.

National discount chain (part of the Baltic "top!" retail group, product
images served from a shared `etop.lv` asset host). Storefront is an
Angular app rendered server-side (Angular Universal SSR: `_ngcontent-*`
attributes are present in the raw HTML from a cold `curl_cffi` GET, no
Playwright needed). No WAF.

The catalog is not browsed as a plain paginated grid on this pass; the
reachable page is the site's "all promo products" listing,
`/lv/visi-akcijas-produkti`, which server-renders every current-promotion
product on one page inside `<app-product-box-preview>` components:

    <app-product-box-preview>
      <img class="default-img" alt="NAME_UPPER" ...>
      <div class="euros"><span>PRICE</span></div>
      <p class="product-name"> Name Mixed Case </p>
    </app-product-box-preview>

Caution: a naive substring count over this page is badly misleading — the
inlined critical-CSS `<style>` block repeats class-name selectors like
`.product-card-wrap[_ngcontent-...]` hundreds of times, so counting
`"product-card-wrap"` occurrences in raw text way overstates the product
count (218 substring hits vs. 32 real `<app-product-box-preview>` DOM
elements, confirmed with `scrapy.Selector`). Always parse via CSS/XPath on
this site, never `str.count()` / naive regex over the raw HTML.

No stable per-product id is exposed in the static markup (card navigation
is `jsaction`-driven Angular routing, no `<a href>`); `product_id` is left
null.

Re-verified live 2026-09-06: GET /lv/visi-akcijas-produkti -> 200, 1.66MB,
32 `app-product-box-preview` elements via Selector, e.g. "Čipsi Ādažu Ar
Tomātiem 130g" EUR 1.69 (crossed-out EUR 2.39-2.49).

Gotcha: `www.toppartika.lv` intermittently 301-redirects the *entire* host
(homepage included) to bare `etop.lv` -- confirmed both ways live within
the same session (toppartika.lv serving directly, then minutes later
redirecting every path including `/`). `etop.lv` is not a typo/CDN alias,
it is the platform's real domain (identical page bytes, same Angular app)
and it has resolved consistently across repeated re-checks, so the spider
targets `etop.lv` directly rather than depending on which way the
toppartika.lv redirect happens to be pointing on a given day. Separately:
this host is also TLS-fingerprint-sensitive -- the project-wide default
`chrome120` (`IMPERSONATE_BROWSERS` in settings.py) 301s, `chrome124`
clears -- so `RandomBrowserMiddleware` is disabled in favour of pinning
`chrome124` explicitly (same pattern as `_watsons_base.py` /
`aceuae_ae.py`). Also note: `product_id` is null (no stable id in the
markup), so `url` is given a `#<slug>` fragment per item --
`DuplicationPipeline` dedups on `item["url"]`, and every row sharing the
one page URL verbatim would collapse to a single kept item.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_URL = "https://etop.lv/lv/visi-akcijas-produkti"
_IMPERSONATE_PROFILE = "chrome124"
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class ToppartikaLvSpider(scrapy.Spider):
    name = "toppartika_lv"
    allowed_domains = ["etop.lv"]
    currency = "EUR"
    language = "lv"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            _URL, callback=self.parse_offers, meta={"impersonate": _IMPERSONATE_PROFILE}
        )

    def parse_offers(self, response):
        cards = response.css("app-product-box-preview")
        logger.info(f"toppartika_lv: {len(cards)} promo product cards")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in cards:
            name = card.css("p.product-name::text").get()
            price = card.css(".euros ::text").get()
            if not name or not price:
                continue
            name = name.strip()
            price = price.strip()
            if not name or not price:
                continue
            slug = _SLUG_RE.sub("-", name.lower()).strip("-")
            yield {
                "product_id": None,
                "product_name": name[:500],
                "category": None,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{_URL}#{slug}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
