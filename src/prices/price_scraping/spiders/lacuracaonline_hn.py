"""
Spider for La Curacao Honduras -- https://www.lacuracaonline.com/honduras/.

Electronics/appliances/general-merchandise chain, same multi-country Magento
2 Luma install as lacuracaonline_ni (Nicaragua) -- this spider covers
honduras only, using the sibling /honduras/ path on the same domain.

Live-checked 2026-09-01: /honduras/ is a plain server-rendered Magento 2
Luma storefront (same as /nicaragua/), so MagentoSSRBaseSpider's
product-item-link / data-price-amount regex applies directly. Enumerability
proof: c/electrodomesticos ?p=1 vs ?p=2 returned 24 + 24 fully disjoint
product URLs. Sample: refrigeradora listing showed prices like "L
14,997.00" (data-price-amount="14997"), confirming HNL (Lempira) pricing,
not NIO.

Overrides _item because product PDP URLs on this install end in the literal
segment "/p" (e.g. .../refrigeradora-...-456724600017/p) -- the base
class's default of taking the last path segment as product_id would
collapse every product to the id "p".
"""

import html
import logging
import re

from price_scraping.spiders._magento_base import MagentoSSRBaseSpider

logger = logging.getLogger(__name__)

_CATEGORY_URL_RE = re.compile(
    r'href="(https://www\.lacuracaonline\.com/honduras/c/[a-z0-9\-/]+)"'
)
_SKU_RE = re.compile(r"-(\d+)/p$")


class LacuracaonlineHnSpider(MagentoSSRBaseSpider):
    name = "lacuracaonline_hn"
    allowed_domains = ["lacuracaonline.com", "www.lacuracaonline.com"]
    currency = "HNL"
    language = "es"

    DISCOVERY_URL = "https://www.lacuracaonline.com/honduras/"
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
