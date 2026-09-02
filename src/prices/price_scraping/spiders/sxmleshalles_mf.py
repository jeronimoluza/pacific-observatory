"""
SXM Les Halles (St. Martin, French part) -- https://www.sxmleshalles.com/.

St Martin's FIRST price source of any kind. Online grocery and villa/yacht
provisioning service delivering across both sides of the island; the business
itself is French-side (the PrestaShop page config reports country FR with
call_prefix 33, and the bare domain redirects to /fr/).

PrestaShop 1.7, Tier 1A. Category discovery, pagination and price
normalisation all come from the shared base class unchanged -- 148 categories
are found from the homepage walk, spanning the full grocery range plus an
unusually deep wine and spirits cellar.

    >>> WHY _items IS OVERRIDDEN <<<
    The base's `_items` requires `[itemprop="name"]` and returns early when it
    is absent. This theme ships no schema.org microdata at all: the card is

        article.product-miniature[data-id-product]
          h2.product-title > a      -> name + PDP href
          span.price                -> "$37.00"

    so the base found all 148 category pages (148x HTTP 200) and yielded zero
    items on the first test run. Only the name/url lookup is replaced here;
    price parsing still goes through the base's `normalize_price`. Overriding
    in the subclass rather than adding a `.product-title` fallback to the base
    keeps the ~20 other PrestaShop spiders bit-identical.

    >>> CURRENCY IS USD, NOT THE EUR IN countries.yaml <<<
    The storefront declares its own currency machine-readably:
    {"id":2,"name":"UD Dollar","iso_code":"USD","sign":"$"}, and prices render
    as "$37.00". St Martin (French part) is officially EUR and countries.yaml
    says EUR, but the skill's rule is to take the site's own code over the
    countries.yaml default -- and SXM's provisioning market genuinely quotes
    villa and yacht customers in USD. Recorded so the divergence is not later
    mistaken for a spider bug.
"""

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from price_scraping.spiders._prestashop_base import (
    PrestashopBaseSpider,
    normalize_price,
)


class SxmleshallesMfSpider(PrestashopBaseSpider):
    name = "sxmleshalles_mf"
    allowed_domains = ["sxmleshalles.com", "www.sxmleshalles.com"]
    currency = "USD"
    language = "fr"
    HOME_URL = "https://www.sxmleshalles.com/fr/"
    CARD_CSS = "article.product-miniature"

    def _items(self, c, response):
        name = c.css("h2.product-title a::text").get()
        name = re.sub(r"\s+", " ", name).strip() if name else None
        if not name:
            return

        url = c.css("h2.product-title a::attr(href)").get()
        product_id = c.attrib.get("data-id-product")
        if not product_id and url:
            m = re.search(r"/(\d+)-[a-z0-9\-]+\.html", url)
            product_id = m.group(1) if m else None
        if not product_id:
            return

        price_text = c.css("span.price::text").get()
        price = normalize_price(price_text, self.currency) if price_text else None
        if not price:
            return

        yield {
            "product_id": str(product_id),
            "product_name": name[:500],
            "category": self._category_from_url(url) or self._category_label(response),
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": urljoin(response.url, url) if url else response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _category_from_url(href):
        """Category slug out of /{lang}/<category>/<id>-<slug>.html.

        Preferred over the base's page-level label because the homepage
        carries a large product grid of its own. The base parses HOME_URL as
        a category, so every product reachable from that grid was being
        labelled "Accueil" -- and because DuplicationPipeline dedups on URL,
        whichever page is crawled first wins, which is the homepage. That put
        a useless label on 688 of 2,128 rows (32%) in the first full run,
        while each row's own URL named the real category all along
        (/fr/beaujolais/, /fr/tofu/, /fr/pates-fraiches/, ...). The
        classifier consumes `category`, so this is signal worth recovering.
        """
        if not href:
            return None
        parts = [p for p in href.split("?")[0].split("#")[0].split("/") if p]
        # ['fr', '<category>', '<id>-<slug>.html'] -- need the middle segment
        if len(parts) < 3 or not parts[-1].endswith(".html"):
            return None
        slug = parts[-2]
        if slug in ("fr", "en"):
            return None
        return slug.replace("-", " ").strip() or None
