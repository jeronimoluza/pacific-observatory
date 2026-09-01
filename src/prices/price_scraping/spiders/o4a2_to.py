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


# --- Per-vendor collection spiders -------------------------------------------
# Contributed 2026-09-01 (EAP handoff). These subclass O4a2ToSpider rather than
# ShopifyBaseSpider so they inherit the _PICKUP_SUFFIX strip above; the incoming
# versions did not strip it and shipped 250-row samples whose every name ended
# in 'PICK UP FROM <STORE>'. They select a vendor by Shopify collection
# (PRODUCTS_PATH) instead of `vendor_filter`, which is the cheaper request path
# when the vendor has its own collection URL.
#
# Golden Star and Hihifo are deliberately NOT here: they are already onboarded
# as golden_star_to / hihifo_supermarket_to via vendor_filter, and a second
# manifest over the same shelf would double-count it.


class O4a2ZfCompanyToSpider(O4a2ToSpider):
    """O4A2 vendor collection for Z & F Vava'u Wholesale & Retail."""

    name = "o4a2_zf_company_to"
    PRODUCTS_PATH = "/collections/z-f-company-ltd-neiafu-vavau-falekoloa-hanga-ki-pouono/products.json"


class O4a2AtlasLiquorToSpider(O4a2ToSpider):
    """O4A2 vendor collection for Atlas Liquor, Ha'ateiho."""

    name = "o4a2_atlas_liquor_to"
    PRODUCTS_PATH = "/collections/atlas-liquor/products.json"


class O4a2HotPizzaToSpider(O4a2ToSpider):
    """O4A2 vendor collection for Hot Pizza."""

    name = "o4a2_hot_pizza_to"
    PRODUCTS_PATH = "/collections/hot-pizza/products.json"


class O4a2JuiceLabToSpider(O4a2ToSpider):
    """O4A2 vendor collection for The Juice Lab."""

    name = "o4a2_juice_lab_to"
    PRODUCTS_PATH = "/collections/the-juice-lab/products.json"


class O4a2TropicalTasteToSpider(O4a2ToSpider):
    """O4A2 vendor collection for Tropical Taste, Pahu Nuku'alofa."""

    name = "o4a2_tropical_taste_to"
    PRODUCTS_PATH = "/collections/tropical-taste-pahu-nukualofa-tonga/products.json"


class O4a2GoGasToSpider(O4a2ToSpider):
    """O4A2 vendor collection for Go Gas (LPG)."""

    name = "o4a2_go_gas_to"
    PRODUCTS_PATH = "/collections/go-gas/products.json"
