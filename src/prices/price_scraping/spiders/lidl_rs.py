"""
Spider for Lidl Serbia -- https://www.lidl.rs/.

Same custom Vue SSR storefront platform as lidl_si (see lidl_si.py) --
confirmed by identical numeric category-hub IDs across markets (e.g.
h10095752 = meat, h10071012 = fresh fruit & veg, h10071050 = fish,
h10071049 = frozen food). A prior pass tried Lidl's `assortment`+`locale`
search-API route for Serbia and got stuck 400ing on an undocumented
required parameter -- that whole detour is unnecessary: the same public
`/h/<slug>/h<id>` category hub pages that work for Slovenia are live and
server-rendered on lidl.rs too, no API needed.

Re-verified live 2026-08-07: /h/meso-i-zivina/h10095752 -> 200, 617KB, 29
data-grid-data tiles parsed cleanly, e.g. itemId 10059166 'PIKOK Dimljeni
svinjski vrat' RSD 129.99.

One schema difference from lidl_si: Serbia's tiles carry price directly at
top-level `price.price` / `price.currencyCode` (a flat block), with
`regionsPrices` present but empty -- not the `regionsPrices.1.currentPrice
.price` nesting lidl_si uses. This spider tries both shapes so it survives
either. `online` is false on every sampled item (site is a digital
catalog/leaflet with real current prices, not an e-commerce cart, matching
lidl_si's own "promo-led catalog" note) -- items are still emitted, with
`available` mirroring the `online` flag rather than gating inclusion.

64 /h/ category hub slugs discovered from the homepage's own top nav.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.lidl.rs"
_CATEGORIES = [
    "aku-alati/h10067531",
    "auto-i-motor/h10067538",
    "basta-i-terasa/h10067558",
    "bastenska-oprema-i-bastenski-alati/h10067533",
    "bebe-i-deca/h10096283",
    "biciklizam/h10067544",
    "biljke-i-cvece/h10071024",
    "cipele-i-pribor/h10067569",
    "ciscenje-domacinstva/h10067527",
    "decija-odeca-2-8-godina/h10067575",
    "decija-soba/h10067557",
    "dekoracija/h10067559",
    "dnevna-soba/h10067554",
    "domacinstvo/h10096287",
    "elektricni-alati/h10067532",
    "fitnes/h10067543",
    "gotova-jela/h10071020",
    "gradnja-i-renoviranje/h10067536",
    "grejanje-i-hladenje/h10067566",
    "hodnik-i-ostava/h10067560",
    "igracke/h10067573",
    "kafa-caj-i-kakao/h10071683",
    "kampovanje-outdoor/h10067542",
    "kancelarija/h10067555",
    "koferi-i-dodaci-za-putovanje/h10067572",
    "kuhinja-i-trpezarija/h10067556",
    "kuhinjski-aparati/h10067522",
    "kupatilo/h10067553",
    "kuvanje-i-pecenje/h10067523",
    "lepota-i-nega-tela/h10067563",
    "meso-i-zivina/h10095752",
    "mlecni-proizvodi-i-jaja/h10095761",
    "multimedija-i-tehnika/h10067564",
    "muska-odeca/h10067568",
    "odeca-za-bebe/h10067574",
    "odlaganje-i-organizacija/h10067526",
    "oprema-za-bebe-i-decu/h10067576",
    "oprema-za-ljubimce/h10067551",
    "oprema-za-ljubimce/h10071025",
    "ostava/h10096095",
    "osvetljenje/h10067561",
    "pekara/h10096086",
    "pice/h10071022",
    "pranje-i-peglanje/h10067528",
    "radionica-i-proizvodi-od-gvozda/h10067534",
    "radna-garderoba/h10067537",
    "rostilj-i-pribor/h10067525",
    "rucni-alati/h10067535",
    "skolski-pribor/h10067577",
    "slatkisi-i-grickalice/h10096205",
    "spavaca-soba/h10067552",
    "stolnjaci-i-posude/h10067524",
    "sveza-riba-i-morski-plodovi/h10071050",
    "sveze-voce-i-povrce/h10071012",
    "trcanje/h10067547",
    "ulje-sirce-i-sosevi/h10096110",
    "vino-pivo-i-zestoka-pica/h10096268",
    "vodeni-sportovi/h10067545",
    "zabava-i-timski-sportovi/h10067548",
    "zamrznuta-hrana/h10071049",
    "zdravlje-i-lepota/h10096275",
    "zdravlje-i-wellness/h10067549",
    "zenska-odeca/h10067567",
    "zitarice-i-namazi/h10096153",
]

_DATA_GRID_RE = re.compile(r'data-grid-data="')


class LidlRsSpider(scrapy.Spider):
    name = "lidl_rs"
    allowed_domains = ["lidl.rs"]
    currency = "RSD"
    language = "sr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for path in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/h/{path}",
                callback=self.parse_category,
                meta={"category": path.split("/")[0]},
            )

    def parse_category(self, response):
        category = response.meta["category"]
        text = response.text
        n_parsed = 0
        scraped_at = datetime.now(timezone.utc).isoformat()
        for m in _DATA_GRID_RE.finditer(text):
            start = m.end()
            end = text.find('"', start)
            if end == -1:
                continue
            raw = text[start:end]
            try:
                data = json.loads(html.unescape(raw))
            except ValueError:
                continue
            if not isinstance(data, dict) or "itemId" not in data:
                continue
            item = self._item(data, category, scraped_at)
            if item:
                n_parsed += 1
                yield item
        logger.info(f"lidl_rs: {category} items={n_parsed}")

    def _price(self, data: dict):
        # lidl_si shape: regionsPrices.1.currentPrice.price (or
        # .currentLidlPlusPrice.price.price for loyalty-only items).
        region = (data.get("regionsPrices") or {}).get("1") or {}
        price_block = region.get("currentPrice")
        if isinstance(price_block, dict) and isinstance(
            price_block.get("price"), (int, float)
        ):
            return price_block["price"]
        plus_block = region.get("currentLidlPlusPrice")
        nested = plus_block.get("price") if isinstance(plus_block, dict) else None
        if isinstance(nested, dict) and isinstance(nested.get("price"), (int, float)):
            return nested["price"]
        # lidl_rs shape: flat top-level price.price.
        flat = data.get("price")
        if isinstance(flat, dict) and isinstance(flat.get("price"), (int, float)):
            return flat["price"]
        return None

    def _item(self, data: dict, category: str, scraped_at: str):
        price = self._price(data)
        if price is None:
            return None
        name = data.get("fullTitle") or ""
        return {
            "product_id": str(data.get("itemId") or data.get("erpNumber") or ""),
            "product_name": html.unescape(name).strip()[:500],
            "category": data.get("category") or category,
            "price": str(price),
            "currency": self.currency,
            "available": bool(data.get("online", True)),
            "url": f"{_BASE}{data.get('canonicalPath', '')}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
