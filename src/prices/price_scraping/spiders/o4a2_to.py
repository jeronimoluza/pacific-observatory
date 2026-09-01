"""O4A2 (https://o4a2.com) -- Tonga online grocery-delivery platform on
Shopify. Shopify.country="TO", Shopify.currency active="NZD" (confirmed
2026-09-01). Functions as a directory: distinct named Tongan retailers
(Golden Star Supermarket & Wholesale, Hihifo Supermarket - Fo'ui, Pingi
Store Ha'apai, Rainbow Top - Market, Z&F Vava'u Wholesale & Retail, ...)
each carry their own catalog under the shared Shopify `vendor` field, sold
for pickup/delivery to family in Tonga. Per the onboard-price-sources
marketplace-as-directory doctrine, each named retailer is onboarded as its
own source rather than one blended "marketplace" catalog -- filter by
`vendor_filter` (spider_kwargs) so one manifest = one real retailer.
"""

import re

from price_scraping.spiders._shopify_base import ShopifyBaseSpider

# Every O4A2 listing appends the collection point to the product title, e.g.
# 'Sack of Flour 25kg - "PICK UP FROM GOLDEN STAR, VAVA\'U"'. The suffix is
# constant per vendor, so it is pure boilerplate: it carries no product
# information and would otherwise reach the COICOP classifier, which reads
# product_name. Strip it and keep the product part.
_PICKUP_SUFFIX = re.compile(
    r"""\s*[-\u2013\u2014]?\s*["\u201c\u2018']?\s*PICK\s*UP\s*FROM\b.*$""", re.I | re.S
)


class O4a2ToSpider(ShopifyBaseSpider):
    name = "o4a2_to"
    allowed_domains = ["o4a2.com"]
    base_url = "https://o4a2.com"
    currency = "NZD"
    language = "en"
    vendor_filter: str | None = None  # set via YAML spider_kwargs

    def _items(self, p: dict):
        if self.vendor_filter and (p.get("vendor") or "").strip() != self.vendor_filter:
            return
        for item in super()._items(p):
            name = item.get("product_name") or ""
            cleaned = _PICKUP_SUFFIX.sub("", name).strip(
                " -\u2013\u2014\"\u201c\u201d'"
            )
            if cleaned:
                item["product_name"] = cleaned
            yield item
