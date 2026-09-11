"""Pulse Pharmacy -- https://pulse.co.bw/.

Standard WooCommerce Store API. Probed 2026-09-11: HTTP 200, real
Gaborone pharmacy SKUs. Catalog is genuinely tiny -- confirmed via both
the Store API (per_page=100 returns exactly 4 items, one page) and the
sites own Yoast product-sitemap.xml (4 loc entries, same 4 products).
One of the four ("Mpumelelo Products") carries price=0 and is dropped by
the shared WooBase zero-price guard, leaving 3 real priced rows: African
Dawn Teas Assorted 40s (BWP 21.95), Berocca Boost Eff 20s (BWP 154.95),
Easywaves Coconut Hair food (BWP 7.95). currency_code=BWP, minor_unit=2,
matches countries.yaml. Kept in the repo despite falling short of the
usual 5-row acceptance bar per the wave-5 breadth-over-depth guidance --
see batch_18_report.md for the explicit call-out.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class PulseBwSpider(WooBaseSpider):
    name = "pulse_bw"
    allowed_domains = ["pulse.co.bw"]
    currency = "BWP"
    language = "en"
    BASE_URL = "https://pulse.co.bw/wp-json/wc/store/v1/products"
