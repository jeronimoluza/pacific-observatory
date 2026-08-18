"""
Spider for Continente (Portugal) — https://www.continente.pt.

Salesforce Commerce Cloud storefront, fully server-rendered. Every product
tile on a department listing page carries a
`data-product-tile-impression='{"name":...,"id":...,"price":...,"brand":...,
"category":...}'` JSON attribute — analytics bait, but a complete
structured record straight in the raw HTML (no JS needed).
Re-verified live 2026-08-06: GET https://www.continente.pt/mercearia/ ->
HTTP 200, 2.2MB, 36 tiles matched. Sample: 'Atum Posta em Óleo sem Glúten
Bom Petisco' EUR 1.54; 'Massa Esparguete Nº5 Barilla' EUR 1.08. Pagination
via ?start=N (36 results/page, e.g. ?start=36 -> next 35-36 products,
confirmed live); `data-total-count` on the first page of each department
gives the stop point (Mercearia alone: 5,401 products). Walks all 16
first-party product departments (frescos, mercearia, laticinios-e-ovos,
congelados, bebidas-e-garrafeira, limpeza, beleza-e-higiene, bio-e-saudavel,
bebe, animais, casa-e-jardim, casa-bricolage-e-jardim, desporto-e-viagem,
brinquedos-e-jogos, papelaria, livros) — excludes non-catalogue pages
(folhetos, oportunidades, marcas, black-friday, etc).
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_DEPARTMENTS = [
    "frescos",
    "mercearia",
    "laticinios-e-ovos",
    "congelados",
    "bebidas-e-garrafeira",
    "limpeza",
    "beleza-e-higiene",
    "bio-e-saudavel",
    "bebe",
    "animais",
    "casa-e-jardim",
    "casa-bricolage-e-jardim",
    "desporto-e-viagem",
    "brinquedos-e-jogos",
    "papelaria",
    "livros",
]
_PAGE_SIZE = 36
_MAX_START = 6000  # guardrail; largest department seen live is ~5.4k
_TILE_RE = re.compile(r"data-product-tile-impression='([^']+)'")
_TOTAL_RE = re.compile(r'data-total-count="(\d+)"')


class ContinentePtSpider(scrapy.Spider):
    name = "continente_pt"
    allowed_domains = ["continente.pt"]
    currency = "EUR"
    language = "pt"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def _request(self, dept: str, start: int):
        url = f"https://www.continente.pt/{dept}/?start={start}&sz={_PAGE_SIZE}"
        return scrapy.Request(
            url, callback=self.parse_page, meta={"dept": dept, "start": start}
        )

    async def start(self):
        for dept in _DEPARTMENTS:
            yield self._request(dept, 0)

    def parse_page(self, response):
        dept = response.meta["dept"]
        start = response.meta["start"]
        body = response.text
        tiles = _TILE_RE.findall(body)
        if not tiles:
            return
        for raw in tiles:
            item = self._item(html.unescape(raw), dept)
            if item:
                yield item
        total_m = _TOTAL_RE.search(body)
        total = int(total_m.group(1)) if total_m else None
        next_start = start + _PAGE_SIZE
        if next_start >= _MAX_START:
            return
        if total is not None and next_start >= total:
            return
        yield self._request(dept, next_start)

    def _item(self, raw_json: str, dept: str):
        try:
            data = json.loads(raw_json)
        except ValueError:
            return None
        name = (data.get("name") or "").strip()
        price = data.get("price")
        pid = str(data.get("id") or "")
        if not name or price is None or not pid:
            return None
        return {
            "product_id": pid,
            "product_name": name[:500],
            "category": data.get("category") or dept,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"https://www.continente.pt/on/demandware.store/Sites-continente-Site/default/Product-Show?pid={pid}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
