"""
Spider for CroCart (Croatia) — https://www.cro-cart.hr/cijene.

Cross-retailer price-comparison aggregator: CroCart downloads the official
daily price lists (cjenici) of 5 Croatian chains (Lidl, Kaufland, Spar,
Plodine, Eurospin) and republishes them as 23 fixed commodity comparison
pages (/cijene/<slug>, e.g. /cijene/mlijeko), each server-rendering an HTML
table of matched products with the cheapest price and the retailer that
offers it.

Re-verified live 2026-08-06: GET /cijene/mlijeko -> 200, 56KB SSR HTML,
table rows like 'Dukat Mlijeko UHT 2,8% m.m. 1 L' | '0,85 €' | '0,85 €/L' |
'Plodine'. No further pagination — each commodity page renders its full
comparison table in one response.

Note: this yields the single lowest price + attributed retailer per product,
not a full per-retailer price matrix (the "(+N)" marker means N other
retailers also stock it, at a price not shown here).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.cro-cart.hr"
_SLUGS = [
    "banane",
    "brasno",
    "cokolada",
    "deterdzent",
    "jabuke",
    "jaja",
    "jogurt",
    "kava",
    "kruh",
    "krumpir",
    "maslac",
    "med",
    "piletina",
    "pivo",
    "riza",
    "sampon",
    "secer",
    "sir",
    "tjestenina",
    "toaletni-papir",
    "ulje",
    "voda",
    "vrhnje",
]
_ROW_RE = re.compile(
    r'<span class="font-medium">([^<]+)</span>'
    r'<span class="text-muted-foreground text-xs ml-2">([^<]*)</span></td>'
    r'<td class="px-4 py-3 font-semibold whitespace-nowrap">([0-9.,]+)\s*€</td>'
    r'<td class="px-4 py-3 text-muted-foreground hidden sm:table-cell whitespace-nowrap">[^<]*</td>'
    r'<td class="px-4 py-3 text-muted-foreground hidden md:table-cell">([^<]+)<span'
)


class CrocartHrSpider(scrapy.Spider):
    name = "crocart_hr"
    allowed_domains = ["cro-cart.hr"]
    currency = "EUR"
    language = "hr"

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
        for slug in _SLUGS:
            yield scrapy.Request(
                f"{_BASE}/cijene/{slug}",
                callback=self.parse_page,
                meta={"slug": slug},
            )

    def parse_page(self, response):
        slug = response.meta["slug"]
        rows = _ROW_RE.findall(response.text)
        logger.info(f"crocart_hr: {slug} rows={len(rows)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for name, size, price, retailer in rows:
            product_name = name.strip()
            if size.strip():
                product_name = f"{product_name} ({size.strip()})"
            product_id = f"{slug}:{name.strip()}"
            yield {
                "product_id": product_id,
                "product_name": product_name[:500],
                "category": slug,
                "price": price.replace(",", "."),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}/cijene/{slug}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
                "attributed_retailer": retailer.strip(),
            }
