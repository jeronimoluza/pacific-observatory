"""CMC Wholesaler (Guam) -- https://cmcwholesalerguam.com/shop/.

Food-service wholesale distributor (bakery/packaging/grocery supplies sold in
bulk case units). WooCommerce Store API is registered under the OLDER
namespace /wp-json/wc/store/products -- the standard /wc/store/v1/products
path 404s on this tenant (rest_no_route). Confirmed via /wp-json/ namespace
list: 'wc/store' present, no 'wc/store/v1'. Prices are integer minor units;
the Store API's currency_minor_unit field rescales them (raw 7340 -> $73.40,
verified against the rendered price_html on the same payload)."""

from price_scraping.spiders._woo_base import WooBaseSpider


class CmcWholesalerGuamSpider(WooBaseSpider):
    name = "cmcwholesalerguam"
    allowed_domains = ["cmcwholesalerguam.com"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://cmcwholesalerguam.com/wp-json/wc/store/products"
