"""
KeretaBrunei — https://www.keretabrunei.com/, "Buy and sell cars,
motorbikes and trucks in Brunei". Vehicle classifieds marketplace built
on the CarGebeya Rails platform (confirmed by the `_CarGebeya_session`
cookie).

Discovery lead re-probed 2026-09-06: the public-facing routes
(`/buy-car-<make>`, `/en/ads`) return a literal JSON body `null` to a
plain GET -- looks dead at first glance, and the site's own sitemap-style
pages (`/sitemap/car`) enumerate the full worldwide make/model taxonomy
with almost no real inventory behind most entries. The catalog IS real,
confirmed via the RSS "last ad" feed (`/en/last_ad`) showing a live
listing ("Toyota Vios for sale ... BND 7,500"). The `/en/ads` endpoint is
a Turbolinks/jQuery AJAX partial: it only returns real content when
called with `X-Requested-With: XMLHttpRequest` and an
`Accept: text/javascript` header, at which point it responds with a
`$('#ads-list').html('...')` JS-string blob containing escaped listing-
card HTML -- a plain browser UA/Accept header alone gets the `null` stub
that made the site look empty.

Pagination via `?page=N` on the same AJAX endpoint, confirmed disjoint
(distinct ad ids page-to-page).

Card markup (post-unescape): `<a class="common-ad-card ..." href="/en/
vehicle_listings/ad-<slug>-<id>">` wrapping `<h4 title="<year> <make>
<model>">` and, when priced, `<div class="ad-vehicle-price">...<span
class="price">7,000</span></div>` under a `BND` label (confirmed from the
ad-detail page's own currency dropdown: BND/USD only, BND is the
storefront default -- matches countries.yaml for brunei_darussalam).
~80% of cards on a sampled page carry a price; unpriced ("POA"/inquire)
ads are skipped.

CAVEAT: used-vehicle classifieds asking prices, not new-vehicle retail
list prices -- same caveat class as bruneida_bn/khmer24_kh/olx_ba for
secondhand-goods marketplaces.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.keretabrunei.com"
MAX_PAGES = 5  # safety cap
CARD_SPLIT = '<a class="common-ad-card'
HREF_RE = re.compile(r'href="([^"]*)"')
TITLE_RE = re.compile(r'<h4 title="([^"]*)"')
PRICE_RE = re.compile(r'<span class="price">([\d,]+)</span>')
ID_RE = re.compile(r"-(\d+)$")


class KeretabruneiBnSpider(scrapy.Spider):
    name = "keretabrunei_bn"
    allowed_domains = ["keretabrunei.com"]
    currency = "BND"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "DEFAULT_REQUEST_HEADERS": {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": (
                "text/javascript, application/javascript, "
                "application/ecmascript, application/x-ecmascript, */*; q=0.01"
            ),
        },
    }

    async def start(self):
        yield scrapy.Request(
            self._url(1), callback=self.parse_page, meta={"page": 1}
        )

    @staticmethod
    def _url(page: int) -> str:
        return f"{_BASE}/en/ads?listing%5Bcar_type%5D=1&page={page}"

    def parse_page(self, response):
        page = response.meta["page"]
        text = response.text
        m = re.search(r"\$\('#ads-list'\)\.html\('(.*)'\);\s*$", text, re.S)
        if not m:
            logger.warning(f"{self.name}: page={page} no ads-list blob found")
            return
        blob = m.group(1).replace("\\'", "'").replace('\\"', '"').replace("\\/", "/")
        cards = blob.split(CARD_SPLIT)[1:]
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for card in cards:
            href_m = HREF_RE.search(card)
            title_m = TITLE_RE.search(card)
            price_m = PRICE_RE.search(card)
            if not (href_m and title_m and price_m):
                continue
            try:
                price = float(price_m.group(1).replace(",", ""))
            except ValueError:
                continue
            if price <= 0:
                continue
            href = href_m.group(1)
            id_m = ID_RE.search(href.rstrip("/"))
            n += 1
            yield {
                "product_id": id_m.group(1) if id_m else None,
                "product_name": title_m.group(1).strip()[:500],
                "category": "vehicle",
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}{href}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: page={page} priced_cards={n} total_cards={len(cards)}")

        if cards and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                self._url(nxt), callback=self.parse_page, meta={"page": nxt}
            )
