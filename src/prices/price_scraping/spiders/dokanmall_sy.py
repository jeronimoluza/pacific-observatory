"""
Dokan Mall (Syria) -- https://dokan.com.sy/.

Standard WooCommerce Store API. General online mall (phones, beauty,
small electronics, home/decor, health & medical aids, kitchenware) --
confirmed via category sample: 'الإلكترونيات' (electronics), 'الصحة
والتغذية' (health & nutrition), 'المطبخ والسفرة' (kitchen), 'الجمال
والعطور' (beauty & perfumes), 'أدوات تحسين البيت' (home improvement).
Broad, multi-division catalog -- classified dept-store, not marketplace
(single WooCommerce tenant, not a seller directory).

NOT a duplicate of the already-onboarded dokan_sy (www.dokan.sy): that
source runs a completely different Laravel/'AIZ' storefront template
(aiz-card-box markup, /search2 AJAX endpoint, USD diaspora
gift/remittance catalog -- top-ups, flowers, Sham Cash transfers).
dokan.com.sy is plain WooCommerce, prices natively in SYP, and does not
redirect to or mirror dokan.sy (confirmed live 2026-09-11: dokan.com.sy
and www.dokan.com.sy both resolve to their own 200/329KB homepage,
zero AIZ/Laravel markers). Only the generic brand word 'دكان' (Arabic for
'shop') is shared.

Verified live 2026-09-11: x-wp-total=4048, x-wp-totalpages=203 at
per_page=20. Page 1 vs page 2 returned disjoint product-id sets (20 each,
zero overlap) -- genuine pagination.

Currency: Store API reports currency_code=SYP consistently (checked pages
1-2, 40 products sampled, zero USD). Matches Syria's country currency, no
FORCE_CURRENCY needed. currency_minor_unit=0 (e.g. price "840" -> SYP
840, not 8.40) -- confirmed against the card's own price_html on the same
row.

Page family: API (Store API JSON; permalinks are real PDP URLs but never
fetched by this spider).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class DokanmallSySpider(WooBaseSpider):
    name = "dokanmall_sy"
    allowed_domains = ["dokan.com.sy", "www.dokan.com.sy"]
    currency = "SYP"
    language = "ar"
    BASE_URL = "https://dokan.com.sy/wp-json/wc/store/v1/products"
