"""Master Fashion -- https://masterfashion.co.bw/.

Standard WooCommerce Store API. Probed 2026-09-11: 607 products total
(600 across 6 full pages of 100 + 7 on page 7), fashion/perfumery
catalog (Lattafa perfumes, caps, belts, shirts). Carries 3 leftover
'ZZTEST' placeholder SKUs (ZZTEST Cap/Belt/Shirt) out of 607 -- negligible
noise, left as-is rather than filtered since they still have real
non-zero prices and the classifier will route them harmlessly.
currency_code=BWP, minor_unit=2, matches countries.yaml. Pagination
verified distinct at per_page=5: page1 ids {43568,43569,44795,44796,44797}
vs page2 ids {43563,43564,43565,43566,43567}, zero overlap.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class MasterfashionBwSpider(WooBaseSpider):
    name = "masterfashion_bw"
    allowed_domains = ["masterfashion.co.bw"]
    currency = "BWP"
    language = "en"
    BASE_URL = "https://masterfashion.co.bw/wp-json/wc/store/v1/products"
