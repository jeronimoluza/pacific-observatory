"""
Spider for Otto.de — large German general-merchandise retailer/marketplace.

Category listing pages (e.g. /damen/mode/hosen/) are server-rendered Svelte
components; each product sits in an `<article class="reptile-tile-item"
data-product-id="...">` block. Only the first ~18-27 cards per page render
with a real price inline (`reptile-price__priceValue`, e.g. "ab  43,99 €");
the remaining ~60 cards on the same page are lazy-load "placeholder" tiles
(name/url present via a `title="..."` attribute, price absent) that only
populate client-side.

Two structural limits ruled out a deeper crawl:
  - Pagination is JS/state-driven only — the visible page-2/3/... controls
    are `<button>` elements with no href, and `?page=2` silently redirects
    back to page 1 (confirmed: identical data-product-id set on both).
  - Product detail pages are behind Kasada bot-protection (KPSDK challenge,
    HTTP 400 on a plain fetch) even though category listing pages are not,
    so there is no PDP fallback for the placeholder cards' prices.
Both confirmed live 2026-08-17.

Given that, this scopes to many leaf categories x one page each (the only
page reachable), keeping only cards with a real price. See manifest notes
for the full category list and the resulting row count.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.otto.de"

CATEGORIES = [
    "damen/mode/hosen/",
    "damen/mode/kleider/",
    "damen/mode/pullover/",
    "herren/mode/hosen/",
    "herren/mode/jacken/",
    "herren/mode/hemden/",
    "haushalt/kuechengeraete/kuechenmaschinen/",
    "haushalt/staubsauger/",
    "haushalt/kuehlschraenke/",
    "haushalt/kaffeemaschinen/",
    "haushalt/mikrowellen/",
    "haushalt/geschirrspueler/",
    "haushalt/backoefen/",
    "haushalt/waeschepflege/buegeleisen/",
    "technik/fernseher/",
    "moebel/betten/",
    "spielzeug/lego/",
    "spielzeug/puppen/",
    "baumarkt/werkzeug/",
    "auto/autozubehoer/",
    "accessoires/uhren/",
    "camping/zelte/",
    "heimtextilien/bettwaesche/",
    "garten/gartenmoebel/",
    "garten/grills/",
    "buerobedarf/tinte-toner/",
    "dekoration/kerzen/",
    "taschen/rucksaecke/",
    "fahrraeder/e-bikes/",
    "koerperpflege/haarpflege/",
]

_CARD_RE = re.compile(r'<article class="reptile-tile-item')
_ID_RE = re.compile(r'data-product-id="(\d+)"')
_HREF_RE = re.compile(r'href="(/p/[^"]+)"')
_TITLE_RE = re.compile(r'title="([^"]*)"')
_PRICE_SPAN_RE = re.compile(
    r'<span class="([^"]*reptile-price__priceValue[^"]*)"[^>]*>([^<]*)</span>'
)
_AMOUNT_RE = re.compile(r"([\d.]+,\d{2})")


def _extract_price(card: str):
    for cls, text in _PRICE_SPAN_RE.findall(card):
        if "strikethrough" in cls:
            continue
        m = _AMOUNT_RE.search(text)
        if m:
            return m.group(1).replace(".", "").replace(",", ".")
    return None


class OttoDeSpider(scrapy.Spider):
    name = "otto_de"
    allowed_domains = ["otto.de", "www.otto.de"]
    currency = "EUR"
    language = "de"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 3,
        "DOWNLOAD_DELAY": 0.7,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for path in CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/{path}",
                callback=self.parse_listing,
                errback=self.errback,
                meta={"category": path.strip("/")},
            )

    def parse_listing(self, response):
        category = response.meta["category"]
        starts = [m.start() for m in _CARD_RE.finditer(response.text)]
        starts.append(len(response.text))
        scraped_at = datetime.now(timezone.utc).isoformat()

        yielded = 0
        for i in range(len(starts) - 1):
            card = response.text[starts[i] : starts[i + 1]]
            id_m = _ID_RE.search(card)
            href_m = _HREF_RE.search(card)
            title_m = _TITLE_RE.search(card)
            price = _extract_price(card)
            if not (id_m and href_m and title_m and price):
                continue
            name = title_m.group(1).strip()
            if not name:
                continue

            yield {
                "product_id": id_m.group(1),
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": urljoin(_BASE, href_m.group(1)),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            yielded += 1
        logger.info(f"otto_de: category={category} yielded={yielded}")

    def errback(self, failure):
        logger.error(
            f"otto_de request failed: {failure.request.url} — {failure.value!r}"
        )
