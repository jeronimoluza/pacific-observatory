"""
Kokkoya Organics (Myanmar) — https://kokkoyaorganics.com/.

Standard Shopify storefront (Canopy theme). Confirmed `Shopify.currency =
{"active":"MMK"}` and `Shopify.country = "MM"` in the homepage bootstrap JS —
this is a Myanmar-based farm-to-table / organic grocer, not a diaspora store.
Small catalogue (~105 SKUs): fresh produce, dairy/cheese, eggs, coffee/tea,
jams, sauces, bread — genuinely food-and-beverage led with a handful of
non-food ancillary items (compost, cooler bag, laundry liquid, a card game).
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class KokkoyaOrganicsMmSpider(ShopifyBaseSpider):
    name = "kokkoya_organics_mm"
    allowed_domains = ["kokkoyaorganics.com"]
    base_url = "https://kokkoyaorganics.com"
    currency = "MMK"
    language = "en"
