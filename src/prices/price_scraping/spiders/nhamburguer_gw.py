"""NHA PEDIDO / Nhamburguer (Bissau, Guinea-Bissau) -- grocery + restaurant catalogue.

A Bissau storefront hosted on the Brazilian white-label platform
meucomercio.com.br (Nextar "NEX-SITE" e-commerce). The merchant record in the
page payload carries the physical address -- Avenida Pansau Na Isna, Bairro de
Santa Luzia, Sector Autonomo de Bissau, Guine-Bissau (11.8747, -15.5913) -- so
despite the .com.br host this is a domestic Guinea-Bissau retailer.

Probed 2026-09-12. The storefront HTML is Next.js SSR and embeds only the first
20 products, and `?page=N` is ignored server-side, so the rendered pages are not
enumerable. A Playwright network trace of the in-page search box exposed the
backing API:

    POST https://api.ecommerce.nextar.com/api/v2/prod/products
    headers: client: NEX-SITE, shop-code: 2229531, token: <static site token>
    body:    {"filter": {"category": "", "subCategory": "", "search": "",
                         "sort": {"ProductName": 1}, "page": N,
                         "perPage": N, "onlyPromo": false, ...}}

It answers over plain HTTP with no cookie or session warm-up, so Playwright runs
only at discovery time and never at collection time.

Pagination gotcha: the API IGNORES `page` entirely -- page=0/1/2/3 all return the
same window. `perPage` is the only lever that moves, and it is honoured up to the
full catalogue, so the spider issues ONE request with perPage=_PER_PAGE and
treats a short page as the whole catalogue. Do not "fix" this into a page loop:
a loop would re-emit the same first N products forever.

Currency: the rendered storefront prints FCFA and `SalePrice` is already in
whole francs -- ADOCANTE PINGO DOCE 300 COMPRIMIDOS reads SalePrice=1000.0
against a rendered "FCFA 1,000". No minor-unit scaling (XOF has none). The API
payload carries no currency field at all, so XOF is set at the class level.

Catalogue observed 2026-09-12: 3,793 products, 3,737 priced, across 44
categories -- food (ALIMENTACAO DOCE 764, ALIMENTACAO SALGADA 575, LACTICINIOS
112, LEGUMES & FRUTAS 46, TALHO carnes, PASTELARIA, PIZZAS), drink (GARRAFEIRA
441, SUMOS/NECTARES 72, REFRIGERANTE 60, AGUA 29, CAFES 42, ENERGETICO 14),
household (LIMPEZA LAR 265, PAPEL/DESCARTAVEIS 309, INSECTICIDA 13, BAZAR 14),
personal care (HIGIENE PESSOAL 364, PRODUTOS CAPILARES 171, PERFUMES 114, CREME
CORPORAL 37), baby (CUIDA BEBE 66, ALM BEBE 29) and PARAFARMACIA 21.

`PromoSalePrice` is deliberately NOT used as the price: several rows carry a
promo price whose `PromoEndAt` is years in the past (the platform never clears
them), so `SalePrice` is the only field that is reliably the current shelf
price.
"""

import json
import re
import unicodedata
from datetime import datetime, timezone

import scrapy

API_URL = "https://api.ecommerce.nextar.com/api/v2/prod/products"
SHOP_CODE = "2229531"
STORE_SLUG = "nhamburguer"
STORE_BASE = "https://meucomercio.com.br"
# Static, site-wide token shipped in the public JS bundle (base64
# "linxintegrationtoken") -- not a per-user credential.
SITE_TOKEN = "bGlueGludGVncmF0aW9udG9rZW4="
# One shot, sized well above the observed 3,793-product catalogue. The API
# ignores `page`, so this is the only way to reach the whole catalogue.
PER_PAGE = 20000


def _slug(name: str) -> str:
    """Reproduce the storefront's product-URL slug from the product name."""
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s


class NhamburguerGwSpider(scrapy.Spider):
    name = "nhamburguer_gw"
    allowed_domains = ["api.ecommerce.nextar.com", "meucomercio.com.br"]
    currency = "XOF"
    language = "pt"
    source_label = "nhamburguer_gw"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "DOWNLOAD_TIMEOUT": 180,
        "ROBOTSTXT_OBEY": False,
    }

    def _headers(self) -> dict:
        return {
            "client": "NEX-SITE",
            "shop-code": SHOP_CODE,
            "token": SITE_TOKEN,
            "content-type": "application/json",
            "accept": "application/json, text/plain, */*",
            "origin": STORE_BASE,
            "referer": f"{STORE_BASE}/",
        }

    async def start(self):
        body = {
            "filter": {
                "category": "",
                "subCategory": "",
                "search": "",
                "lowStock": False,
                "stockControl": False,
                "sort": {"ProductName": 1},
                "page": 1,
                "perPage": PER_PAGE,
                "onlyPromo": False,
                "sortFilter": "A-Z",
            }
        }
        yield scrapy.Request(
            API_URL,
            method="POST",
            headers=self._headers(),
            body=json.dumps(body),
            callback=self.parse_catalogue,
            dont_filter=True,
        )

    def parse_catalogue(self, response):
        try:
            products = response.json().get("list") or []
        except ValueError:
            self.logger.warning("non-JSON response at %s", response.url)
            return
        self.logger.info("%s catalogue size=%d", self.name, len(products))
        for p in products:
            item = self._item(p)
            if item:
                yield item

    def _item(self, p: dict):
        price = p.get("SalePrice")
        try:
            value = float(price)
        except (TypeError, ValueError):
            return None
        # A zero price is a placeholder (menu headers, unpriced kitchen items),
        # not a price observation.
        if value <= 0:
            return None

        name = str(p.get("ProductName") or "").strip()
        if not name:
            return None

        cat = p.get("Category") or None
        sub = p.get("SubCategory") or None
        category = " > ".join(x.strip() for x in (cat, sub) if x and x.strip()) or None

        pid = p.get("ProductId")
        url = (
            f"{STORE_BASE}/{STORE_SLUG}/product/{_slug(name)}/{pid}"
            if pid is not None
            else ""
        )

        return {
            "product_id": str(p.get("BarCode") or p.get("ProductCode") or pid),
            "product_name": name[:500],
            "category": category,
            "price": str(value),
            "currency": self.currency,
            "available": not bool(p.get("Inactive")),
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
