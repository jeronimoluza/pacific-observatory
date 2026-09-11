"""236 Shopping -- https://236shopping.com/.

Shopify products.json catalog for the Central African Republic. "236" is the
country's international dialling code, and the store brands itself "votre
boutique en ligne 100% centrafricaine"; every product title is suffixed
"a Bangui RCA", so the catalog is unambiguously priced for Bangui rather than
for a diaspora audience abroad.

Probed 2026-09-11: 96 products total. Pagination verified distinct at
limit=50 -- page1 50 ids, page2 46 ids, zero overlap, page3 empty. XAF read
from the storefront's own currency field; 2 of 96 products carry a zero price
and are dropped by the base class. Assortment is home goods -- furniture,
bedding, small appliances, childcare.

Found on the second ddgs pass, not the first: a generic "online grocery
<country>" sweep returned nothing for CAR at all, and this surfaced only when
the queries switched to French-language local phrasing ("acheter en ligne
Republique Centrafricaine", "boutique en ligne Bangui").
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class Shopping236CfSpider(ShopifyBaseSpider):
    name = "shopping236_cf"
    allowed_domains = ["236shopping.com"]
    base_url = "https://236shopping.com"
    currency = "XAF"
    language = "fr"
