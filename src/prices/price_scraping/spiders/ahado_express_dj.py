"""Spider for AHADO EXPRESS (Djibouti) — https://ahadoexpress.net/.

Static site whose catalog is client-rendered from a public Google Sheets gviz
endpoint, not a normal REST API. Traced js/main.js -> js/data-loader.js ->
js/config.js for the sheet id, then hit the gviz endpoint directly:
https://docs.google.com/spreadsheets/d/1WnLMz5rtsKa0cCmbqNN_Fh3d_5nm99kJVmzrN4427-Y/gviz/tq?tqx=out:json&sheet=Produits

Re-verified live 2026-08-06: HTTP 200, 44KB gviz-wrapped JSON, 174 rows.
Each row is one product with up to 3 pack-size tiers (label + price), e.g.
'Bio' -> '1 paquet' 500 FDJ / 'Pack (x6)' 2900 FDJ / 'Pack (x12)' 5700 FDJ.
One item is emitted per populated tier. Product names/labels are French, so
language is set to 'fr' (overriding the shard's cfg_lang=en, which reflects
the site's UI chrome, not the catalog itself).

The response is not plain JSON — it's wrapped in a JS callback
(`/*O_o*/\ngoogle.visualization.Query.setResponse({...});`) that must be
stripped before parsing.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1WnLMz5rtsKa0cCmbqNN_Fh3d_5nm99kJVmzrN4427-Y/gviz/tq"
    "?tqx=out:json&sheet=Produits"
)
_WRAPPER_RE = re.compile(r"setResponse\((.*)\);?\s*$", re.S)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _cell(c):
    return c.get("v") if c else None


def _slug(text: str) -> str:
    return _SLUG_RE.sub("_", text.strip().lower()).strip("_")


class AhadoExpressDjSpider(scrapy.Spider):
    name = "ahado_express_dj"
    allowed_domains = ["docs.google.com"]
    currency = "DJF"
    language = "fr"

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
        yield scrapy.Request(_URL, callback=self.parse)

    def parse(self, response):
        m = _WRAPPER_RE.search(response.text)
        if not m:
            logger.warning("ahado_express_dj: gviz wrapper not found")
            return
        try:
            obj = json.loads(m.group(1))
        except ValueError:
            logger.warning("ahado_express_dj: gviz payload not valid JSON")
            return
        rows = obj.get("table", {}).get("rows", [])
        logger.info(f"ahado_express_dj: rows={len(rows)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for r in rows:
            cells = r.get("c", [])
            if len(cells) < 12:
                continue
            vals = [_cell(c) for c in cells]
            category, name, _popular, _icon = vals[0], vals[1], vals[2], vals[3]
            tiers = [(vals[4], vals[5]), (vals[6], vals[7]), (vals[8], vals[9])]
            statut = vals[11]
            if not name:
                continue
            available = not (
                isinstance(statut, str) and statut.strip().lower().startswith("expir")
            )
            for label, price in tiers:
                if price is None or label is None:
                    continue
                product_name = html.unescape(f"{name} - {label}").strip()[:500]
                product_id = _slug(f"{name}_{label}")
                yield {
                    "product_id": product_id,
                    "product_name": product_name,
                    "category": html.unescape(category).strip() if category else None,
                    "price": str(price),
                    "currency": self.currency,
                    "available": available,
                    "url": f"https://ahadoexpress.net/#{product_id}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }
