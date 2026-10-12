"""Andorra Informatica (Andorra) -- https://www.andorrainformatica.com/.

Andorran computing / electronics retailer (+376 contact details). PrestaShop
with `id-slug` category URLs, so the shared base discovers categories; the
`article.product-miniature` cards carry no schema.org microdata, so only the
card parser is overridden. Price is the text of `.product-price-and-shipping
.price` ("493,75 €").
"""

import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

from price_scraping.spiders._prestashop_base import (
    PrestashopBaseSpider,
    normalize_price,
)


class AndorrainformaticaAdSpider(PrestashopBaseSpider):
    name = "andorrainformatica_ad"
    allowed_domains = ["andorrainformatica.com"]
    currency = "EUR"
    language = "es"
    HOME_URL = "https://www.andorrainformatica.com/"
    CARD_CSS = "article.product-miniature"

    def _items(self, c, response):
        name = c.css(".product-title a::text").get()
        name = re.sub(r"\s+", " ", name).strip() if name else None
        href = c.css(".product-title a::attr(href)").get()
        pid = c.attrib.get("data-id-product")
        if not (name and href and pid):
            return
        attr = c.attrib.get("data-id-product-attribute")
        text = c.css(".product-price-and-shipping .price::text").get()
        price = normalize_price(text, self.currency) if text else None
        if not price:
            return
        m = re.match(r"/([a-z0-9\-]+)/\d+-", urlsplit(href).path)
        yield {
            "product_id": f"{pid}-{attr}" if attr and attr != "0" else pid,
            "product_name": name[:500],
            "category": m.group(1).replace("-", " ") if m else None,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": urljoin(response.url, href),
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
