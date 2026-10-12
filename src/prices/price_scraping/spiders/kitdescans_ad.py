"""Kit d'Ans (Andorra) -- https://kitdescans.com/.

Andorran furniture and bedding retailer (AD500, +376). PrestaShop with the iqit theme and clean category URLs (no `id-slug`), so
the shared base's category discovery finds nothing; this subclass takes the
top-level single-segment menu links as categories instead. Cards are
`article.product-miniature`; the price is the `content` attribute of
`.product-price` (decimal, avoids the "1.234,56 €" format). `?page=N`
pagination comes from the base.
"""

import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import scrapy

from price_scraping.spiders._prestashop_base import PrestashopBaseSpider

_HREF_RE = re.compile(r'href="(https?://[^"#?\s]+)"')
_SKIP_RE = re.compile(
    r"(compte|account|cart|cistella|carrito|llista|desitjos|inscri|contact|"
    r"condicion|conditions|legal|privacy|privacidad|cookie|blog|content|"
    r"mapa|sitemap|combinacions|mes-venuts|mas-vendidos|novedades|novetats|"
    r"datos-personales|formas-de-pago|amp)",
    re.IGNORECASE,
)


class KitdescansAdSpider(PrestashopBaseSpider):
    name = "kitdescans_ad"
    allowed_domains = ["kitdescans.com"]
    currency = "EUR"
    language = "ca"
    HOME_URL = "https://kitdescans.com/"
    CARD_CSS = "article.product-miniature"

    def _new_category_requests(self, response):
        host = urlsplit(self.HOME_URL).netloc.removeprefix("www.")
        for url in sorted(set(_HREF_RE.findall(response.text))):
            parts = urlsplit(url)
            segs = [s for s in parts.path.split("/") if s]
            if (
                parts.netloc.removeprefix("www.") != host
                or len(segs) != 1
                or len(segs[0]) < 3
                or "." in segs[0]
                or _SKIP_RE.search(segs[0])
                or url in self.seen_categories
            ):
                continue
            self.seen_categories.add(url)
            yield scrapy.Request(
                url, callback=self.parse_category, meta={"page": 1, "cat_url": url}
            )

    def _items(self, c, response):
        name = c.css(".product-title a::text").get()
        name = re.sub(r"\s+", " ", name).strip() if name else None
        href = c.css(".product-title a::attr(href)").get()
        pid = c.attrib.get("data-id-product")
        if not (name and href and pid):
            return
        attr = c.attrib.get("data-id-product-attribute")
        price = c.css(".product-price::attr(content)").get()
        try:
            if not price or float(price) <= 0:
                return
        except ValueError:
            return
        cat = c.css(".product-category-name::text").get()
        yield {
            "product_id": f"{pid}-{attr}" if attr and attr != "0" else pid,
            "product_name": name[:500],
            "category": cat.strip() if cat and cat.strip() else None,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": urljoin(response.url, href),
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
