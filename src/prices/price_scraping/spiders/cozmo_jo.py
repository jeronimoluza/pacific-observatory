"""Cozmo (Jordan) -- https://cozmo.jo/. THE Group's online supermarket
chain, Amman -- founded 2003, real physical stores with an online catalog
(groceries, household, baby, back-to-school, homeware).

Custom PHP storefront, NOT a known platform (WooCommerce/Magento/Shopify --
0 wp-json / wc hits). Server-rendered category AND product-detail pages
embed the full product record (numeric id, title, price, sku) directly as
HTML attributes on every `div.item.productID` card:
`productID="130034" data-title="Kitco Nice Salted Potato Chips 40g"
data-price="0.4" data-sku="6290340400507"`, with the canonical PDP path in
a sibling `div.card-body a::attr(href)`. Category listing pages already
carry this full data for every product shown on them, so a single-hop
crawl over category/product links (no separate per-PDP fetch) is enough --
confirmed by comparing a leaf category's static curl_cffi fetch against a
Playwright scroll-to-bottom render of the same URL: identical card count
(15 markup nodes / 7-8 unique products), i.e. not JS-paginated for this
leaf.

JOD 3-decimal check (rule: JOD = 1000 fils): PDP for "Kitco Bites Cheese
Balls Corn Puffs 16g" (SKU 6287006940842, productID 129368) renders
on-site as `<p class="new-price"><sup>JD</sup>0.1 <span class="minQty">
per Piece</span></p>` -- i.e. JD 0.100 (100 fils), matching
`data-price="0.1"` on the same card. Parsed as a plain float this is
already correct (0.1 JOD); there is no integer-minor-unit trap here -- the
site's own display elides trailing zeros, it does not omit the decimal
point.

Products carry duplicate markup per page (mobile + desktop card variants)
but both link to the same canonical PDP url, so DuplicationPipeline's
url-based dedup collapses them for free.
"""

import re
from datetime import datetime, timezone

import scrapy
from scrapy.linkextractors import LinkExtractor

_BASE = "https://cozmo.jo"

# Account / checkout / marketing / content paths -- not catalog.
_DENY_PATHS = [
    r"/about-cozmo",
    r"/careers",
    r"/contact-us",
    r"/cozmo-csr-initiatives",
    r"/security-privacy",
    r"/terms-condition",
    r"/checkout",
    r"/myAccount",
    r"/myOrders",
    r"/myAddresses",
    r"/myProfile",
    r"/loyaltyCard",
    r"/logout",
    r"/login",
    r"/register",
    r"/shoppingCart",
    r"/deliveryAddress",
    r"/deliveryDateAndTime",
    r"/onlinePayment",
    r"/payment",
    r"/orderPlaced",
    r"/taxFreeCard",
    r"/allRecipes",
    r"/recipe",
]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class CozmoJoSpider(scrapy.Spider):
    name = "cozmo_jo"
    allowed_domains = ["cozmo.jo"]
    currency = "JOD"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.25,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
        "DEPTH_LIMIT": 4,
    }

    _link_extractor = LinkExtractor(
        allow_domains=["cozmo.jo"],
        deny=_DENY_PATHS,
        deny_extensions=["pdf", "jpg", "jpeg", "png", "svg", "gif", "css", "js"],
        unique=True,
    )

    async def start(self):
        yield scrapy.Request(f"{_BASE}/", callback=self.parse)

    def parse(self, response):
        if not hasattr(response, "css"):
            return

        for card in response.css("div.item.productID"):
            # lxml/libxml2 lowercases HTML attribute names on parse, so the
            # site's `productID="..."` attribute surfaces as `productid`.
            product_id = card.attrib.get("productid")
            title = card.attrib.get("data-title")
            price = card.attrib.get("data-price")
            sku = card.attrib.get("data-sku")
            if not product_id or not title or price is None:
                continue

            href = card.css("div.card-body a::attr(href)").get()
            if not href:
                continue
            if href.startswith("javascript"):
                continue
            url = response.urljoin(href)

            path_segments = [p for p in url.split("cozmo.jo/", 1)[-1].split("/") if p]
            category = (
                path_segments[-2]
                if len(path_segments) >= 2
                else (path_segments[0] if path_segments else None)
            )

            yield {
                "product_id": product_id,
                "product_name": _clean(title),
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                "sku": sku,
            }

        for link in self._link_extractor.extract_links(response):
            yield response.follow(link.url, callback=self.parse)
