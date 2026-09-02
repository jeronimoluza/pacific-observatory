"""Spider for Carrefour Andorra 2000 (Andorra) --
https://alimentacio.andorra2000.ad/.

Classic OpenCart (`route=product/category&path=<id[_<id>...]>`), so category
discovery reuses the shared `_opencart_base.py` NAV_URL leaf-walk. The theme
overrides product-card anchors with a JS quickview handler
(`onclick="quickview('<product_id>')"`) instead of a normal `href` to the PDP
-- the base class's generic `_item()` falls back to the *category* URL when
no href is present, which would collide every product on a page onto one
`product_id`. This subclass overrides `_item()` to pull the real numeric id
out of the onclick attribute and build the PDP URL
(`index.php?route=product/product&product_id=<id>`) directly, confirmed live
to render the same product (title matches, e.g. "CARREFOUR AIGUA AMB GAS
1,25L").
"""

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from price_scraping.spiders._opencart_base import (
    OpencartBaseSpider,
    PRICE_SELECTORS,
    normalize_price,
)

_QUICKVIEW_RE = re.compile(r"quickview\('?(\d+)'?\)")


class Andorra2000AdSpider(OpencartBaseSpider):
    name = "andorra2000_ad"
    allowed_domains = ["andorra2000.ad"]
    currency = "EUR"
    language = "ca"
    NAV_URL = "https://alimentacio.andorra2000.ad/"
    LIMIT = 100

    def _item(self, card, response):
        onclick = card.css("a.cursorpointer::attr(onclick)").get() or ""
        m = _QUICKVIEW_RE.search(onclick)
        if not m:
            return super()._item(card, response)
        product_id = m.group(1)

        name = card.css("div.caption div.name a::text").get()
        if not name or not name.strip():
            return None

        price_text = None
        for sel in PRICE_SELECTORS:
            val = card.css(sel).get()
            if val and val.strip():
                price_text = val
                break
        price = normalize_price(price_text) if price_text else None
        if not price:
            return None
        try:
            if float(price) <= 0:
                return None
        except ValueError:
            return None

        full_url = urljoin(
            response.url,
            f"/index.php?route=product/product&product_id={product_id}",
        )

        return {
            "product_id": product_id,
            "product_name": name.strip()[:500],
            "category": self._category_label(response),
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": full_url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
