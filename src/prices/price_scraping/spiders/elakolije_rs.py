"""
Spider for eLakolije (Univerexport) -- https://elakolije.rs/.

Largest DOMESTIC Serbian supermarket chain (190+ stores). Bespoke PHP
storefront; the mega-menu on the homepage SSRs every category link
directly (`/<categoryId>/polica/<slug>`, ~284 unique category ids across
all tree levels, with item counts shown inline e.g. "TRADICIONALNO VOĆE
(11)") but the product listing itself (`#artikli_lista`) is an empty
placeholder filled by client-side JS.

A Playwright network trace (2026-09-06) of a leaf category page found:
  `POST https://elakolije.rs/api/api.php?action=artikli`
  body: `{"sifkla":"<categoryId>","si_kat":"","datum":"","p_nadji":"",
  "sort":"","si_art":"","ulogovan_kor":"","offset":0,"limit":200}`
  headers: `x-api-key: <static client key>`, `x-requested-with:
  XMLHttpRequest`, `content-type: application/json`.

The x-api-key is a static value baked into the page's own JS (not a
per-session token) and works cold with no cookies. `limit=200` safely
exceeds every observed leaf's true count (e.g. category 1000110
"Tradicionalno voce" returns exactly 11 rows with limit=200, matching
the menu's own "(11)" count), so no offset pagination is needed. Walking
the full ~284-id list (mixed levels, not leaf-only) causes some
redundant category hits but no bad data -- the dedup pipeline keys on
each product's own PDP `link`, so a product surfacing under both a
parent and child category id collapses to one record.

Verified live: category 1000110 -> "JABUKA AJDARED" 149.99 RSD/kg.
"""

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import unquote_plus

import scrapy

logger = logging.getLogger(__name__)

_HOME_URL = "https://elakolije.rs/"
_API_URL = "https://elakolije.rs/api/api.php?action=artikli"
_API_KEY = (
    "Vi3NmguyYAnZKTgBdFPOgIEls0gNYrMF97w4l9L5YvYiBaeEh3SgkBFSX8RKmCM"
    "hJzDqulrklCXtppjSpt6he0x7iOYU7hUxvxAlnr54dUUhgcHziMdiopaPR8gSLIji"
)
_LEAF_LINK_RE = re.compile(r"href='https://elakolije\.rs/(\d+)/polica/[^']*'")


class ElakolijeRsSpider(scrapy.Spider):
    name = "elakolije_rs"
    allowed_domains = ["elakolije.rs"]
    currency = "RSD"
    language = "sr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.7,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_HOME_URL, callback=self.parse_home)

    def parse_home(self, response):
        cat_ids = sorted(set(_LEAF_LINK_RE.findall(response.text)))
        logger.info("elakolije_rs: %d category ids from mega-menu", len(cat_ids))
        for cat_id in cat_ids:
            yield self._api_request(cat_id)

    def _api_request(self, cat_id: str):
        body = {
            "sifkla": cat_id,
            "si_kat": "",
            "datum": "",
            "p_nadji": "",
            "sort": "",
            "si_art": "",
            "ulogovan_kor": "",
            "offset": 0,
            "limit": 200,
        }
        return scrapy.Request(
            _API_URL,
            method="POST",
            body=json.dumps(body),
            headers={
                "x-api-key": _API_KEY,
                "x-requested-with": "XMLHttpRequest",
                "content-type": "application/json",
            },
            callback=self.parse_products,
        )

    def parse_products(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning("elakolije_rs: bad JSON at %s", response.url)
            return
        for row in payload.get("response") or []:
            item = self._item(row)
            if item:
                yield item

    def _item(self, row: dict):
        name = (row.get("naziv") or "").strip()
        product_id = str(row.get("si_art") or "")
        price = row.get("cena")
        if not name or not product_id or price in (None, "", 0):
            return None
        category = row.get("proizvodKategorija")
        category = unquote_plus(category) if category else None
        return {
            "product_id": product_id,
            "product_name": name.replace("\n", " ").strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": row.get("link") or _HOME_URL,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
