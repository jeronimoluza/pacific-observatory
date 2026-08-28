"""
Spider for La Curacao Nicaragua -- https://www.lacuracaonline.com/nicaragua/.

Electronics/appliances/general-merchandise chain, also serving
honduras/guatemala/el_salvador under sibling /<country>/ paths on the same
domain -- this spider covers nicaragua only; the others are future sources.

The bare domain root is a genuinely empty LcoSplash country-picker page
(confirms the onboarding probe's read), and GraphQL/REST are firewalled
(403 "GraphQL disabled" from a Varnish edge). But one path segment deeper,
/nicaragua/ is a plain server-rendered Magento 2 Luma storefront -- not a
headless/SPA front -- so MagentoSSRBaseSpider's product-item-link /
data-price-amount regex applies directly (live-checked 2026-08-17:
c/electrodomesticos/cafeteras ?p=1 vs ?p=2 return disjoint product URLs;
price C$1,529.00 renders as data-price-amount="1529", currency NIO).

Overrides _item because product PDP URLs on this install end in the literal
segment "/p" (e.g. .../cafetera-...-470883400011/p) -- the base class's
default of taking the last path segment as product_id would collapse every
product to the id "p".
"""

import html
import logging
import re

from price_scraping.spiders._magento_base import MagentoSSRBaseSpider

logger = logging.getLogger(__name__)

_CATEGORY_URL_RE = re.compile(
    r'href="(https://www\.lacuracaonline\.com/nicaragua/c/[a-z0-9\-/]+)"'
)
_SKU_RE = re.compile(r"-(\d+)/p$")


class LacuracaonlineNiSpider(MagentoSSRBaseSpider):
    name = "lacuracaonline_ni"
    allowed_domains = ["lacuracaonline.com", "www.lacuracaonline.com"]
    currency = "NIO"
    language = "es"

    DISCOVERY_URL = "https://www.lacuracaonline.com/nicaragua/"
    CATEGORY_URL_RE = _CATEGORY_URL_RE
    MAX_PAGES = 60

    def _item(self, url: str, name: str, price: str):
        name = name.strip()
        if not name or not price:
            return None
        m = _SKU_RE.search(url)
        product_id = m.group(1) if m else url.rstrip("/").rsplit("/", 2)[-2]
        item = super()._item(url, name, price)
        if item:
            item["product_id"] = product_id
            item["product_name"] = html.unescape(item["product_name"])
        return item
