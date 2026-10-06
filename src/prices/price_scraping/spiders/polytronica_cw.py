"""
Polytronica Curacao -- https://polytronicacuracao.com/

Willemstad (Schottegatweg Oost) electronics / appliances retailer on
WordPress + WooCommerce. The Store API is locked (401 rest_forbidden), so
this reads the server-rendered /shop/ listing (25+ pages of 12-ish cards).

WAF NOTE: the host 403s chrome120/chrome124/safari17_0 (5768-byte stub)
and serves 200 only on firefox133. IMPERSONATE_BROWSERS is narrowed to
firefox133 so RandomBrowserMiddleware cannot clobber the profile.

CURRENCY: the storefront renders the florin sign (&fnof;) and has not
migrated to XCG; same 1:1 peg, recorded as ANG as the site shows it.
A sale card carries <del>old</del><ins>current</ins>; the current price is
the <ins> amount.

Page family: listing.
"""

import re
from urllib.parse import urlparse

import scrapy

_CARD = "li.product"
_MAX_PAGES = 100


class PolytronicaCwSpider(scrapy.Spider):
    name = "polytronica_cw"
    allowed_domains = ["polytronicacuracao.com"]
    currency = "ANG"
    language = "en"
    BASE = "https://polytronicacuracao.com/shop/"

    custom_settings = {
        "IMPERSONATE_BROWSERS": ["firefox133"],
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
    }

    def start_requests(self):
        yield self._req(1)

    def _req(self, page):
        url = self.BASE if page == 1 else f"{self.BASE}page/{page}/"
        return scrapy.Request(
            url,
            callback=self.parse_listing,
            meta={"impersonate": "firefox133", "page": page},
            dont_filter=True,
        )

    def parse_listing(self, response):
        cards = response.css(_CARD)
        for card in cards:
            href = card.css("a.woocommerce-LoopProduct-link::attr(href)").get()
            name = card.css("h2.woocommerce-loop-product__title::text").get()
            amt = card.css(
                "span.price ins .woocommerce-Price-amount bdi::text, "
                "span.price > .woocommerce-Price-amount bdi::text"
            ).getall()
            price = None
            if amt:
                price = amt[-1] if card.css("span.price ins") else amt[0]
                price = re.sub(r"[^\d.,]", "", price).replace(",", "")
            if not (href and name and price):
                continue
            classes = card.attrib.get("class", "")
            cats = re.findall(r"product_cat-([\w-]+)", classes)
            pid = card.css("a.add_to_cart_button::attr(data-product_id)").get() or (
                urlparse(href).path.strip("/").split("/")[-1]
            )
            item = {}
            item["product_id"] = pid
            item["product_name"] = name.strip()
            item["price"] = price
            item["currency"] = self.currency
            item["category"] = cats[-1].replace("-", " ") if cats else None
            item["url"] = href
            item["language"] = self.language
            item["available"] = "outofstock" not in classes
            yield item
        page = response.meta["page"]
        if cards and page < _MAX_PAGES and response.css("a.next.page-numbers"):
            yield self._req(page + 1)
