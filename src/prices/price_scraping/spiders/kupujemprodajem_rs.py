"""
KupujemProdajem (Serbia) -- https://www.kupujemprodajem.com/.

Serbia's largest general classifieds marketplace (name translates to
"I buy, I sell"). Server-rendered Next.js pages -- no anti-bot, plain
curl_cffi clears every category page at 200.

Homepage lists ~66 top-level category links
(`/<slug>/kategorija/<id>`), including `nekretnine-izdavanje` (real
estate for rent) and `nekretnine-prodaja` (for sale) alongside the usual
electronics/appliances/vehicles/furniture categories. A CrawlSpider
follows these.

Each category page embeds its ad cards directly in the HTML (CSS-module
class names carry a build-specific hash suffix, e.g.
`AdItemCard-module-scss-module__ypB8EW__price` -- matched with a `\\w+`
wildcard rather than the exact hash since that will rotate on deploys):

    .../<breadcrumb>/oglas/<id>   -- ad permalink + numeric id
    ...__adName">Title</a>        -- ad title
    ...__price...">130 €</div>    -- price text, either "<amount> €" or
                                      "<amount> din" (RSD), or the
                                      non-numeric "Kontakt"/"Kupujem"
                                      (contact-for-price / want-to-buy ads)

Verified live 2026-09-06: bela-tehnika-i-kucni-aparati (white goods)
category returned 195 ad cards in one fetch, mixing EUR (~41%) and RSD
(~55%) listings plus a handful of non-priced "Kontakt"/"Kupujem" rows
(dropped). Amounts use "." as a thousands separator (e.g. "1.210 €" =
EUR 1210), no decimals observed.

coicop_classification: classifier -- general classifieds, no single
COICOP prefix (durables, vehicles, furniture, real-estate rentals all
mixed). channel: marketplace (seller-authored titles).
"""

import logging
import re

import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

logger = logging.getLogger(__name__)

_AD_ID_RE = re.compile(r"/oglas/(\d+)\"")
_AD_NAME_RE = re.compile(
    r'AdItemCard-module-scss-module__\w+__adName"[^>]*>([^<]+)</a>'
)
_AD_PRICE_RE = re.compile(
    r'AdItemCard-module-scss-module__\w+__price[^"]*">([^<]*)</div>'
)
_AD_HREF_RE = re.compile(r'href="(/[^"]+/oglas/\d+)"')
_PRICE_VAL_RE = re.compile(r"^([\d.]+)\s*(€|din)$")


class KupujemprodajemRsSpider(CrawlSpider):
    name = "kupujemprodajem_rs"
    allowed_domains = ["kupujemprodajem.com"]
    start_urls = ["https://www.kupujemprodajem.com/"]
    language = "sr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEPTH_LIMIT": 2,
        "DOWNLOAD_TIMEOUT": 60,
    }

    rules = (
        Rule(
            LinkExtractor(allow=r"/kategorija/\d+$"),
            callback="parse_category",
            follow=False,
        ),
    )

    def parse_category(self, response):
        blocks = re.split(
            r'<div class="AdItemCard-module-scss-module__\w+__container">',
            response.text,
        )[1:]
        found = 0
        for b in blocks:
            item = self._item(b)
            if item:
                found += 1
                yield item
        logger.info(f"{self.name}: {response.url} ads_yielded={found} of {len(blocks)}")

    def _item(self, block):
        id_m = _AD_ID_RE.search(block)
        name_m = _AD_NAME_RE.search(block)
        price_m = _AD_PRICE_RE.search(block)
        href_m = _AD_HREF_RE.search(block)
        if not (id_m and name_m and price_m and href_m):
            return None

        price_val_m = _PRICE_VAL_RE.match(price_m.group(1).strip())
        if not price_val_m:
            return None  # "Kontakt" / "Kupujem" / unparsable
        amount_str, symbol = price_val_m.groups()
        try:
            amount = float(amount_str.replace(".", ""))
        except ValueError:
            return None
        if amount <= 0:
            return None
        currency = "EUR" if symbol == "€" else "RSD"

        return {
            "product_id": id_m.group(1),
            "product_name": name_m.group(1).strip()[:500],
            "price": str(amount),
            "currency": currency,
            "category": None,
            "url": "https://www.kupujemprodajem.com" + href_m.group(1),
            "available": True,
            "language": self.language,
        }
