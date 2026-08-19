"""
Spider for Lidl Slovenia — https://www.lidl.si/.

Custom Vue SSR storefront (data-v-* attributes). The homepage/category
"sereca" promo widgets only embed a curated dozen items, but the 46 `/h/`
category hub pages (site's own top nav, e.g. /h/meso-in-perutnina/h10095752)
server-render a full grid of product tiles, each carrying a
`data-grid-data="{&quot;...&quot;}"` attribute: an HTML-entity-escaped JSON
blob with itemId, fullTitle, and pricing. Re-verified live 2026-08-06:
/h/meso-in-perutnina/h10095752 -> 200, 928KB, 48/48 tiles parsed cleanly,
e.g. itemId 11002048 'GRILLMEISTER Nurnberske pecenice XXL' 4.99 EUR.

Price lives at regionsPrices.1.currentPrice.price (plain EUR float); items
that are Lidl-Plus-loyalty-exclusive only have currentLidlPlusPrice instead
(we fall back to that so those items aren't dropped, at the cost of using
the loyalty price rather than a regular price that doesn't exist for them).

No further pagination was found beyond each hub page's first SSR batch --
?page=2 returns byte-identical itemIds, and the "Nalozi vec izdelkov" button
is a client-side infinite-scroll load driven by an unidentified XHR call, so
this walk is 46 SSR'd pages, not the deep-paginated full catalog.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.lidl.si"
_CATEGORIES = [
    "ciscenje-v-gospodinjstvu/h10067527",
    "dekoracija/h10067559",
    "delavnica-in-orodje/h10067534",
    "dojencki-in-otroci/h10096283",
    "gospodinjstvo/h10096287",
    "gotove-jed/h10071020",
    "gradnja-in-prenova/h10067535",
    "gradnja-in-prenova/h10067536",
    "hisni-ljubljencki/h10067551",
    "hodnik-in-shramba/h10067560",
    "igrace-in-igre/h10067573",
    "iz-shrambe/h10096095",
    "kava-caj-in-kakav/h10071683",
    "kopalnica/h10067553",
    "kosmici-in-namazi/h10096153",
    "kuhanje-in-peka/h10067523",
    "kuhinjski-aparati/h10067522",
    "lepota-in-nega-telesa/h10067563",
    "meso-in-perutnina/h10095752",
    "mlecni-izdelki-in-jajca/h10095761",
    "moska-oblacila/h10067568",
    "multimedija-in-tehnologija/h10067564",
    "olja-kis-in-omake/h10096110",
    "oprema-za-dojencke-in-otroke/h10067576",
    "otroska-oblacila-2-8-let/h10067575",
    "pekarna/h10096086",
    "pijace/h10071022",
    "pisarna/h10067555",
    "pripomocki-za-zivali/h10071025",
    "razsvetljava/h10067561",
    "ribe-in-morski-sadezi/h10071050",
    "roze-in-rastline/h10071024",
    "sadje-in-zelenjava/h10071012",
    "shranjevanje-in-organizacija/h10067526",
    "sladkarije-in-prigrizki/h10096205",
    "sola-in-ustvarjalnost/h10067577",
    "spalnica/h10067552",
    "vino-pivo-in-zgane-pijace/h10096268",
    "vrt-in-balkon/h10067558",
    "vrtno-orodje-in-oprema/h10067533",
    "zabavne-igre-in-skupinski-sporti/h10067548",
    "zamrznjena-hrana/h10071049",
    "zar-in-dodatki/h10067525",
    "zdravje-in-dobro-pocutje/h10067549",
    "zdravje-in-lepota/h10096275",
    "zenska-moda/h10067567",
]

_DATA_GRID_RE = re.compile(r'data-grid-data="')


class LidlSiSpider(scrapy.Spider):
    name = "lidl_si"
    allowed_domains = ["lidl.si"]
    currency = "EUR"
    language = "sl"

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
        logger.info(f"lidl_si: {category} items={n_parsed}")

    def _item(self, data: dict, category: str, scraped_at: str):
        region = (data.get("regionsPrices") or {}).get("1") or {}
        # currentPrice is flat ({"price": 4.99, ...}); currentLidlPlusPrice wraps
        # price one level deeper ({"price": {"price": 0.4, ...}, "lidlPlusText": ...}).
        price_block = region.get("currentPrice")
        if isinstance(price_block, dict):
            price = price_block.get("price")
        else:
            plus_block = region.get("currentLidlPlusPrice")
            nested = plus_block.get("price") if isinstance(plus_block, dict) else None
            price = nested.get("price") if isinstance(nested, dict) else None
        if not isinstance(price, (int, float)):
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
