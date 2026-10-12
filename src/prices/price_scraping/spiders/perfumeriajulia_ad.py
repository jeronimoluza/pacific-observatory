"""Perfumeria Julia (Andorra) -- https://www.perfumeriajulia.ad/.

Andorran perfumery / beauty retailer (.ad domain, +376 contact numbers).
PrestaShop with a custom theme: `article.product-miniature` cards carry no
schema.org microdata, so this subclass keeps the shared base's `id-slug`
category discovery and `?page=N` pagination and overrides only the card
parser. The headline price is `.product-miniature-info-price .price` (the
struck-out `.regular-price` is the pre-discount list price and is ignored).
"""

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from price_scraping.spiders._prestashop_base import (
    PrestashopBaseSpider,
    normalize_price,
)


class PerfumeriajuliaAdSpider(PrestashopBaseSpider):
    name = "perfumeriajulia_ad"
    allowed_domains = ["perfumeriajulia.ad"]
    currency = "EUR"
    language = "ca"
    HOME_URL = "https://www.perfumeriajulia.ad/"
    CARD_CSS = "article.product-miniature"

    def _items(self, c, response):
        name = c.css(".product-miniature-info-name h2::text").get()
        name = re.sub(r"\s+", " ", name).strip() if name else None
        href = c.css(".product-miniature-info-name").xpath("ancestor::a[1]/@href").get()
        pid = c.attrib.get("data-id-product")
        if not (name and href and pid):
            return
        attr = c.attrib.get("data-id-product-attribute")
        text = " ".join(c.css(".product-miniature-info-price .price ::text").getall())
        price = normalize_price(text, self.currency) if text.strip() else None
        if not price:
            return
        yield {
            "product_id": f"{pid}-{attr}" if attr and attr != "0" else pid,
            "product_name": name[:500],
            "category": self._category_label(response),
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": urljoin(response.url, href),
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
