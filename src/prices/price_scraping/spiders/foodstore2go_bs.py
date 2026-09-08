"""
Foodstore2Go (The Bahamas) -- https://foodstore2go.com/.

Vanilla Shopify storefront; /products.json?limit=250&page=N confirmed live
2026-09-05: 862 products across 4 pages, disjoint per page, clean
termination. Nassau / Paradise Island grocery delivery operator ("Foodstore2Go
delivers groceries across the Bahamas to hotels, Airbnbs, marinas & vacation
rentals in Nassau & Paradise Island" -- its own meta description).

Catalogue is food-led at real Bahamian shelf prices: fresh produce
(Cauliflower 6.25, Grapefruit 2.75, Kiwi 2.75), dairy (Kraft shredded
cheeses, Lactaid), pantry (Campbell's, Prego, Smucker's), bakery mixes, and
a substantial COICOP-02 tail (Kalik Bottles 33.60, Modelo suitcase, Maker's
Mark, Patron, Woodbridge). A small non-food minority exists (a handful of
"simple, virtual" spa-service listings -- massages -- sold as add-ons to the
delivery service, plus disposables like plastic cups); they are left in
rather than name-filtered, since the classifier routes them out of division
01/02 on the product name.

Currency: Shopify.currency reports {"active":"USD"}. BSD is pegged 1:1 to
USD and the storefront charges in USD, so USD is recorded rather than the
BSD used by `solomonsfreshmarkets_bs` / `kellysbahamas_bs` (same convention
question, opposite answer, because those platforms declare BSD themselves).

NOT the same source as foodstore2goexpress.com, which is the same operator's
much smaller WooCommerce site: 22 products total, of which only 7 names
overlap this catalogue. That one was rejected as a separate source -- it is
a thin duplicate surface, not additional coverage.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class Foodstore2goBsSpider(ShopifyBaseSpider):
    name = "foodstore2go_bs"
    allowed_domains = ["foodstore2go.com", "www.foodstore2go.com"]
    base_url = "https://foodstore2go.com"
    currency = "USD"
    language = "en"
