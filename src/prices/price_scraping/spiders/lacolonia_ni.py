"""
Spider for Supermercados La Colonia (Nicaragua) - https://lacolonia.com.ni/

Different platform from the pre-existing `lacolonia_hn` (Honduras, VTEX) --
this Nicaragua storefront is a Next.js (App Router) build. Each
`/categoria/<slug>` page server-renders the ENTIRE category's product list as
a JSON array (`initialProducts`) embedded inside a React Server Components
`self.__next_f.push([1,"..."])` script payload -- no separate API call and no
pagination needed, confirmed live: the Abarrotes category alone embeds 2,081
products in one response. We regex out that JSON blob per category page and
parse it directly; Playwright is not required.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)

CATEGORIES = [
    "Abarrotes",
    "Bebes",
    "BebidasAlcoholicas",
    "BebidasYGaseosas",
    "Carnes",
    "Cigarros",
    "CocinaVajilla",
    "Congelado",
    "CuidadoDelHogar",
    "CuidadoPersonal",
    "Embutidos",
    "FerreteriaAuto",
    "FrutasVerduras",
    "LacteosHuevo",
    "Mascotas",
    "Medicamentos",
    "Panaderia",
    "PapelHigienicoYDesechables",
    "TextilesJuguetes",
]


class LacoloniaNiSpider(scrapy.Spider):
    name = "lacolonia_ni"
    allowed_domains = ["lacolonia.com.ni"]
    currency = "NIO"
    language = "es"

    def start_requests(self):
        for cat in CATEGORIES:
            yield scrapy.Request(
                f"https://lacolonia.com.ni/categoria/{cat}",
                callback=self.parse_category,
                meta={"category": cat},
            )

    def parse_category(self, response):
        category = response.meta["category"]
        html = response.text
        products = self._extract_products(html)
        if not products:
            logger.warning(f"lacolonia_ni: no initialProducts found for {category}")
            return
        logger.info(f"lacolonia_ni: {category} -> {len(products)} products")
        for p in products:
            code = p.get("code")
            name = (p.get("name") or "").strip()
            price = p.get("price")
            if not name or price is None:
                continue
            yield {
                "product_id": code,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": f"https://lacolonia.com.ni/producto/{code}"
                if code
                else response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

    @staticmethod
    def _extract_products(html):
        """Locate the `initialProducts` array embedded in a RSC push payload.

        The array itself is JSON but double-escaped (it lives inside a JS
        string literal), so bracket-match on the raw text first, then undo
        the `\\"` -> `"` escaping before handing to json.loads.
        """
        marker = 'initialProducts\\":['
        idx = html.find(marker)
        if idx == -1:
            return []
        start = html.find("[", idx)
        depth = 0
        end = None
        i = start
        while i < len(html):
            ch = html[i]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = i
                    break
            i += 1
        if end is None:
            return []
        raw = html[start : end + 1]
        unescaped = raw.replace('\\"', '"')
        try:
            return json.loads(unescaped)
        except json.JSONDecodeError:
            logger.warning("lacolonia_ni: failed to parse initialProducts JSON")
            return []
