"""
BOMA (Syria) -- https://boma.sy/.

Standard WooCommerce Store API. Despite the assignment brief's 'health'
tag and the homepage <title> ('الصحة الرئيسية - BOMA' -- lit. 'Health
Home - BOMA'), the actual catalog is small kitchen/home electrical
appliances: irons, blenders, microwaves, hand mixers, mini vacuums, air
fryers, water coolers (category sample: 'الأجهزة المنزلية الذكية' smart
home appliances, 'مكواة' irons, 'ميكرويف' microwaves). Classified
electronics, not pharmacy/cosmetics -- 'health' appears to be the site's
generic homepage branding, not the product category.

Verified live 2026-09-11: x-wp-total=83, x-wp-totalpages=83 at
per_page=1 (i.e. 83 products, ~5 pages at per_page=20). Page 1 vs page 2
(per_page=20) returned disjoint product-id sets, zero overlap -- genuine
pagination. Small catalog by design (single-vendor appliance importer);
per the wave-5 brief, breadth of distinct products matters more than
catalog depth here, and a small paginating catalog is not grounds to
skip.

Currency: Store API reports currency_code=USD consistently across the
full catalog (spread-checked pages 1-5 of 20, all 83 products, zero SYP)
-- confirmed genuine, not a display artifact: Syrian storefronts commonly
price imported appliances in USD. No FORCE_CURRENCY needed.
currency_minor_unit=2 (e.g. price "2900" -> USD 29.00).

Page family: API (Store API JSON; permalinks are real PDP URLs but never
fetched by this spider).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class BomaSySpider(WooBaseSpider):
    name = "boma_sy"
    allowed_domains = ["boma.sy", "www.boma.sy"]
    currency = "USD"
    language = "ar"
    BASE_URL = "https://boma.sy/wp-json/wc/store/v1/products"
