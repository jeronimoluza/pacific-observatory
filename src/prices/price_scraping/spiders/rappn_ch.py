"""
Spider for Rappn (Switzerland) -- https://rappn.ch/.

Rappn is an independent Swiss grocery price-comparison platform that
normalises the weekly flyers of seven chains (Migros, Coop, Aldi Suisse,
Lidl Schweiz, Denner, Aligro, Otto's) into one database. Its per-retailer
offer pages are server-rendered Next.js HTML -- no JS execution needed.
The app's own backend (api.rappn.ch) is 403 without app credentials, so
this spider reads the public HTML instead.

Probed live 2026-09-11: GET https://rappn.ch/de/angebote/denner -> HTTP 200,
903KB, 25 offer rows joined name<->price on the offer UUID. Sample:
'Somat Geschirrspultabs All in 1 Extra Zitrone' (Somat, 100 pcs) CHF 16.95.
Each row renders the product name inside
  <a href="/de/angebote-vergleichen/offer/<uuid>" class="line-clamp-2 ...">
and the current price inside a table cell that ends
  >CHF <!-- -->2.95<a href="/de/angebote-vergleichen/offer/<uuid>"
so the UUID is the join key. The struck-through `line-through` span is the
reference price and is deliberately not collected.

Page family parsed: listing (per-retailer offer tables). `category` carries
the retailer slug so downstream can slice by chain. Not an outlet, so the
manifest declares channel: other.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://rappn.ch"
_RETAILERS = [
    "aldi-suisse",
    "aligro",
    "coop",
    "denner",
    "lidl-schweiz",
    "migros",
    "ottos",
]

_UUID = r"([0-9a-fA-F\-]{36})"
_NAME_RE = re.compile(
    r'href="/[a-z]{2}/angebote-vergleichen/offer/' + _UUID + r'"'
    r'[^>]*class="line-clamp-2[^"]*"[^>]*>(.*?)</a>'
    r'(?:\s*<div[^>]*>(.*?)</div>)?',
    re.S,
)
_PRICE_RE = re.compile(
    r">CHF\s*(?:<!--\s*-->)?\s*([\d’',.]+)\s*"
    r'<a href="/[a-z]{2}/angebote-vergleichen/offer/' + _UUID + r'"'
)
_TAG_RE = re.compile(r"<[^>]+>")


def _text(raw: str | None) -> str:
    if not raw:
        return ""
    return html.unescape(_TAG_RE.sub("", raw)).strip()


class RappnChSpider(scrapy.Spider):
    name = "rappn_ch"
    allowed_domains = ["rappn.ch"]
    currency = "CHF"
    language = "de"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "DOWNLOAD_TIMEOUT": 120,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for slug in _RETAILERS:
            yield scrapy.Request(
                f"{_BASE}/de/angebote/{slug}",
                callback=self.parse_offers,
                meta={"retailer": slug},
            )

    def parse_offers(self, response):
        retailer = response.meta["retailer"]
        text = response.text
        names = {}
        for m in _NAME_RE.finditer(text):
            names[m.group(1).lower()] = (_text(m.group(2)), _text(m.group(3)))
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for m in _PRICE_RE.finditer(text):
            uid = m.group(2).lower()
            if uid not in names:
                continue
            name, qualifier = names.pop(uid)
            if not name:
                continue
            price = m.group(1).replace("’", "").replace("'", "").replace(",", ".")
            try:
                float(price)
            except ValueError:
                continue
            full_name = f"{name} {qualifier}".strip() if qualifier else name
            n += 1
            yield {
                "product_id": uid,
                "product_name": full_name,
                "category": retailer,
                "price": price,
                "currency": self.currency,
                "url": f"{_BASE}/de/angebote-vergleichen/offer/{uid}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"rappn_ch: {retailer} items={n}")
