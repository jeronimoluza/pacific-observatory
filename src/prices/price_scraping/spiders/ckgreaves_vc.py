"""
C.K. Greaves & Company (St. Vincent and the Grenadines) —
https://www.ckgreaves.com/.

St Vincent's FIRST price source of any kind — the country had zero manifests
before this pass. C.K. Greaves is a Vincentian grocery chain (founded 1954 on
Upper Bay Street, Kingstown; three locations including Pembroke) running a
genuine full-catalogue webshop: 30 departments / ~15,800 SKUs covering fresh
produce, dairy, meat, seafood, bakery and the full dry-goods range.

Two prior sweeps missed it. The 2026-09-01 LAC inventory recorded St Vincent
as "0 sources, search budget exhausted" after checking only Massy Stores SVG
(brochure-only WordPress, no shop route — re-verified still true here) and
CaribeEats (does not cover VCT). C.K. Greaves was never probed.

Tier 1A — server-rendered WordPress ("supershop" theme), no anti-bot, no JS
needed. robots.txt allows everything except /wp-admin/ and sets no
crawl-delay.

    >>> THE PRICE IS IN AN ATTRIBUTE, NOT THE RENDERED TEXT <<<
    The visible price is split across three elements for typographic effect
    (`<span class="sym">$</span><strong class="dol">4</strong>
      <em class="dec">05</em>`), and the page ALSO renders a literal "$0.00"
    cart-total placeholder. Reading displayed text yields 0.00 or 4 depending
    on the selector — both silently wrong. The card div carries the real
    value as a plain decimal:

        div.product-card[data-price]  -> "4.05"
        div.product-card[data-id]     -> "56018"   internal product id
        div.product-card[data-plu]    -> "0000002002034"  barcode/PLU
        div.product-card[data-url]    -> canonical PDP URL

    Prices are NOT login-gated; the "Please sign in" block is a modal for the
    add-to-cart action only.

Currency is XCD (East Caribbean dollar), declared by the site itself and
matching countries.yaml for st_vincent_and_the_grenadines.

Pagination is /departments/<id>-<slug>/page/N/ at 20 cards per page. Each
department page states its own total ("Showing products 1 - 20 of 201"), so
page 1 reads the total and fans out every remaining page as an independent
request. This is deliberate: a chained page-N -> page-N+1 walk loses the
entire tail of a department to one transient failure, which is exactly how
coop_ci silently truncated at 6,000 rows earlier in this wave.
"""

import logging
import math
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.ckgreaves.com"
START_URL = f"{BASE_URL}/"

_DEPARTMENT_RE = re.compile(r"^/departments/(\d+-[a-z0-9\-]+)/$")
_TOTAL_RE = re.compile(r"Showing\s+products\s+\d+\s*-\s*\d+\s+of\s+([\d,]+)")

PER_PAGE = 20
MAX_PAGES_PER_DEPARTMENT = 200


class CkgreavesVcSpider(scrapy.Spider):
    name = "ckgreaves_vc"
    allowed_domains = ["ckgreaves.com", "www.ckgreaves.com"]
    currency = "XCD"
    language = "en"

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "RETRY_TIMES": 5,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 522, 524, 408],
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            START_URL,
            callback=self.parse_home,
            errback=self.errback,
            dont_filter=True,
        )

    def parse_home(self, response):
        seen = set()
        for href in response.css("a::attr(href)").getall():
            url = urljoin(BASE_URL, href)
            if not url.startswith(BASE_URL):
                continue
            path = url[len(BASE_URL) :].split("?")[0].split("#")[0]
            match = _DEPARTMENT_RE.match(path)
            if not match or match.group(1) in seen:
                continue
            seen.add(match.group(1))
            yield self._page_request(match.group(1), 1)
        logger.info(f"{self.name}: discovered {len(seen)} departments")

    def _page_request(self, dept, page):
        url = f"{BASE_URL}/departments/{dept}/"
        if page > 1:
            url = f"{url}page/{page}/"
        return scrapy.Request(
            url,
            callback=self.parse_department,
            errback=self.errback,
            meta={"dept": dept, "page": page},
            dont_filter=True,
        )

    def parse_department(self, response):
        dept = response.meta["dept"]
        page = response.meta["page"]

        # Fan out the whole department from page 1 rather than chaining.
        if page == 1:
            match = _TOTAL_RE.search(" ".join(response.css("::text").getall()))
            total = int(match.group(1).replace(",", "")) if match else 0
            last = min(
                math.ceil(total / PER_PAGE) if total else 1,
                MAX_PAGES_PER_DEPARTMENT,
            )
            logger.info(f"{self.name}: {dept} total={total} pages={last}")
            for next_page in range(2, last + 1):
                yield self._page_request(dept, next_page)

        category = (
            response.css("h1::text").get() or dept.split("-", 1)[-1].replace("-", " ")
        ).strip()
        cards = response.css("div.product-card")
        found = 0

        for card in cards:
            pid = card.attrib.get("data-id")
            price = card.attrib.get("data-price")
            name = (card.css('h4[itemprop="name"] a::text').get() or "").strip()
            if not pid or not price or not name:
                continue
            try:
                if float(price) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            found += 1
            yield {
                "product_id": card.attrib.get("data-plu") or pid,
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": card.attrib.get("data-url")
                or f"{BASE_URL}/shop/browse/product/{pid}/",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"{self.name}: {dept} page={page} cards={len(cards)} yielded={found}"
        )

    def errback(self, failure):
        logger.warning(f"{self.name}: request failed: {failure.value!r}")
