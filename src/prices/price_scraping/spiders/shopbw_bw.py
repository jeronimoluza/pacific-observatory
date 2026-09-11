"""Shop BW -- https://shopbw.co.bw/.

Standard WooCommerce Store API. Probed 2026-09-11: 240 products total
(100+100+40 across 3 pages), appliances/electronics catalog -- bar
fridges, water dispensers/coolers, camping fridges, kitchen appliances
(Goldair), soundbars/headphones (Philips, Sony), ovens (AEG). API
currency_code=BWP, minor_unit=0 (Pula only, no thebe subunit reported by
this tenant -- prices like 9495/4999 read directly, no division). Matches
countries.yaml. Pagination verified distinct at per_page=5: page1 ids
{8717,8720,8725,8727,8729} vs page2 ids {8697,8700,8707,8710,8713}, zero
overlap.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class ShopbwBwSpider(WooBaseSpider):
    name = "shopbw_bw"
    allowed_domains = ["shopbw.co.bw"]
    currency = "BWP"
    language = "en"
    BASE_URL = "https://shopbw.co.bw/wp-json/wc/store/v1/products"
