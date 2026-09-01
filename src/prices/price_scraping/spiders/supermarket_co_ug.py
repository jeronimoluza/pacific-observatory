"""Spider for Supermarket.co.ug (Uganda) -- https://supermarket.co.ug/.
Cold-start discovery, wave 9. Standard itemprop-tagged PrestaShop category
HTML (/{id}-{slug}), scaffolded on the shared PrestaShop base.

Currency note: the storefront's schema.org markup declares priceCurrency
"RON" (a leftover PrestaShop default currency, not a real Romanian-leu
price) but every visible price and the cart/checkout JSON are rendered in
US dollars ($2.20, $0.49, ...), not UGX -- despite the site delivering
groceries within Kampala/Uganda. This reads as a diaspora-facing "order
groceries for delivery to family in Uganda" model rather than an ordinary
domestic UGX shelf price. Recorded loudly per onboarding rule 8: usable as
a real Uganda-delivering source, but NOT a domestic shelf-price series.
currency is set to USD (what is actually charged), not UGX.
"""

from price_scraping.spiders._prestashop_base import PrestashopBaseSpider


class SupermarketCoUgSpider(PrestashopBaseSpider):
    name = "supermarket_co_ug"
    allowed_domains = ["supermarket.co.ug"]
    currency = "USD"
    language = "en"
    HOME_URL = "https://supermarket.co.ug/"
