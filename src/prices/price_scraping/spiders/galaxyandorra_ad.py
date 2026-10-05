"""Galaxy Andorra -- https://www.galaxyandorra.com/en/.

Andorran photography / electronics shop (AD500, +376), PrestaShop with the
iqit theme. Its `article.product-miniature` cards carry no schema.org
microdata, so the shared base's `_items` (itemprop-driven) emits nothing;
this subclass keeps the base's category discovery and `?page=N` pagination
and overrides only the card parser. Price is the `content` attribute of
`span.product-price` (decimal, e.g. "5639"), which avoids the "EUR5,639.00"
thousands-separator format.
"""

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from price_scraping.spiders._prestashop_base import (
    PrestashopBaseSpider,
    normalize_price,
)


class GalaxyandorraAdSpider(PrestashopBaseSpider):
    name = "galaxyandorra_ad"
    allowed_domains = ["galaxyandorra.com"]
    currency = "EUR"
    language = "en"
    HOME_URL = "https://www.galaxyandorra.com/en/"
    CARD_CSS = "article.product-miniature"

    def _items(self, c, response):
        name = c.css("h3.product-title a::text, .product-title a::text").get()
        name = re.sub(r"\s+", " ", name).strip() if name else None
        href = c.css(".product-title a::attr(href)").get()
        pid = c.attrib.get("data-id-product")
        if not (name and href and pid):
            return
        attr = c.attrib.get("data-id-product-attribute")
        price = c.css(".product-price::attr(content)").get()
        if not price:
            text = c.css(".product-price::text").get()
            price = normalize_price(text, self.currency) if text else None
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
