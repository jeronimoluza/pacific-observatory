"""
Spider for Kibabo Online (Angola) -- https://www.kibabo.co.ao/pt/.

General online supermarket ("Redicom Prolepse" custom CMS -- AngularJS
front-end over server-rendered HTML). Despite the site's own stale meta
description ("loja de produtos nao-alimentares"), the live nav carries a
full grocery department (alimentar, bebidas, frutas-legumes, lacticinios)
alongside non-food departments (higiene, limpeza, electrodomesticos,
brinquedos, casadecoracao, petshop, papelaria, vida-saudavel) -- a genuine
general supermarket catalog, not a non-food-only store.

Category pages (`/pt/<dept>[/<subdept>]_<id>-<catid>.html`, paginated via
`?page=N`) nest three levels deep (department -> subcategory -> leaf) and
themselves list either more subcategories or product URLs
(`/pt/<vendor-slug>/<product-slug>_p<id>.html`) via a schema.org ItemList.
A plain CrawlSpider with two Rules -- one that just keeps following
category/pagination links, one that parses product pages -- walks the
whole tree without hand-coding the hierarchy.

Product pages embed a clean schema.org Product+Offer JSON-LD block with
price as a plain decimal string ("2545.00", priceCurrency "AOA") --
independent of the page's own Portuguese-formatted on-screen price display
("2 545,00 Kz"), so the AOA thousands-separator trap never applies here.
"""

import json
import logging
import re
from datetime import datetime, timezone

from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

logger = logging.getLogger(__name__)

_JSONLD_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL
)


class KibaboAoSpider(CrawlSpider):
    name = "kibabo_ao"
    allowed_domains = ["kibabo.co.ao"]
    start_urls = ["https://www.kibabo.co.ao/pt/"]
    currency = "AOA"
    language = "pt"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    rules = (
        # Product detail pages -- parse.
        Rule(
            LinkExtractor(allow=[r"/pt/[a-z0-9-]+/[a-z0-9-]+_p\d+\.html"]),
            callback="parse_product",
            follow=True,
        ),
        # Department / subcategory / leaf-category listing pages
        # (including `?page=N` pagination) -- just keep following.
        Rule(
            LinkExtractor(
                allow=[r"/pt/[a-z0-9-]+(?:/[a-z0-9-]+)?_\d+-\d+\.html"],
                deny=[
                    r"/login",
                    r"/criar-conta",
                    r"/area-cliente",
                    r"/carrinho",
                    r"/contactos",
                    r"/privacidade",
                    r"/termos",
                    r"/faq",
                    r"/trocas-devolucoes",
                ],
            ),
            follow=True,
        ),
    )

    def parse_product(self, response):
        blocks = _JSONLD_RE.findall(response.text)
        product = None
        for b in blocks:
            try:
                data = json.loads(b)
            except (ValueError, TypeError):
                continue
            if isinstance(data, dict) and data.get("@type") == "Product":
                product = data
                break
        if product is None:
            logger.warning(f"kibabo_ao: no Product JSON-LD at {response.url}")
            return

        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        if price is None:
            logger.warning(f"kibabo_ao: no offer price at {response.url}")
            return

        availability = str(offers.get("availability") or "")
        available = "instock" in availability.lower()

        product_id = str(product.get("sku") or product.get("productID") or response.url)
        product_name = str(product.get("name") or "").strip()
        if not product_name:
            logger.warning(f"kibabo_ao: no product name at {response.url}")
            return

        yield {
            "product_id": product_id,
            "product_name": product_name,
            "category": product.get("category"),
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": available,
            "url": product.get("url") or response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
