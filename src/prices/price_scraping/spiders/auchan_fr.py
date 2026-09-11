"""
Spider for Auchan France -- https://www.auchan.fr/.

Auchan France is a special case among the repo's other Auchan banners
(auchan_ro=VTEX, auchan_pt=SFCC, auchan_sn=PrestaShop, auchan_ua=Zakaz
white-label, auchan_hu=custom sitemap+JSON-LD, alcampo_es=custom
sitemap+JSON-LD+AWS-WAF): every grocery PDP sampled during onboarding
(15/15 across 4 sitemap shards -- dairy, biscuits, pasta, coffee, water,
chocolate, juice) came back `"unavailability_reason":"plus dans la
gamme"` (discontinued/no longer in range) with no price at all, while
non-food PDPs (home, DIY, electronics, toys) are live with real prices.
This matches Auchan France's real-world 2024-2025 retrenchment (most
French hypermarkets sold off) -- **this source is NOT a grocery/
hypermarket feed**, despite the brand. What remains live is a general-
merchandise marketplace: every priced PDP checked carries a named
third-party `seller` in its `productUpdateDetail` JS blob (e.g. "Paris
Prix", "Multishop", "Ropo HX - National", "Nouveaux Marchands") -- never
"Auchan" itself. channel is `marketplace` accordingly, and this is a
real gap: France still has no live online-grocery source in the tree.

Enumerability: https://www.auchan.fr/sitemap.xml -> sitemap-products.xml
-> a 7-way sharded sitemapindex (sitemap-products1..7.xml). Verified live
2026-09-10: shards 1-6 hold 50,000 <loc> each, shard 7 holds 16,601 =
316,601 total product URLs. Shard 1 vs shard 2 full URL sets have ZERO
overlap (alphabetic partition, same convention as auchan_hu/alcampo_es).

PDP is plain server-rendered HTML (no impersonation or Playwright
needed, plain GET -> HTTP 200) but does NOT carry JSON-LD or the
`product:price:amount` OpenGraph meta tag that the shared WooBaseSpider
parse_html fallback chain looks for -- price/currency are schema.org
*microdata* meta tags (`<meta itemprop="price" content="328.99">`,
`<meta itemprop="priceCurrency" content="EUR">`), a form the shared base
class does not parse. Written as a standalone spider rather than
touching that shared file. Name comes from the `og:title` meta tag
(clean product name, no site-suffix to strip, verified across samples).
Category comes from the same page's own `productUpdateDetail` JS blob
(`"category":{"level1":...,"level2":...}`, 1-5 flat keys, order varies)
-- parsed as embedded JSON and joined level1 > level2 > ... > level5 for
whichever levels are present.

Verified 2026-09-10: 'Armoire de chambre 2 portes avec penderie pin
massif naturel ULLI' EUR 328.99 (seller Paris Prix), 'Bandeau led led
strip light rgbic' EUR 33.82 (seller Multishop), 'GP TOYS Figurines
articulees Gormiti...' EUR 29.99 (seller Ropo HX - National), 'GRAF
Recuperateur d'eau 250L Arondo gris graphite' EUR 187.94 (seller
Nouveaux Marchands).
"""

from __future__ import annotations

import html as ihtml
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://www.auchan.fr/sitemaps/sitemap-products.xml"
_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S | re.I)
_PRODUCT_ID_RE = re.compile(r"/pr-([\w-]+)$")
_OG_TITLE_RE = re.compile(r'og:title"\s+content="([^"]*)"')
_PRICE_RE = re.compile(r'itemprop="price"\s+content="([^"]*)"')
_CURRENCY_RE = re.compile(r'itemprop="priceCurrency"\s+content="([^"]*)"')
_CATEGORY_RE = re.compile(r'"category":\{([^{}]*)\}')

MAX_SHARDS = 10  # safety cap; 7 observed live 2026-09-10


class AuchanFrSpider(scrapy.Spider):
    name = "auchan_fr"
    allowed_domains = ["auchan.fr", "www.auchan.fr"]
    currency = "EUR"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_index)

    def parse_index(self, response):
        for loc in _LOC_RE.findall(response.text)[:MAX_SHARDS]:
            yield scrapy.Request(loc, callback=self.parse_shard)

    def parse_shard(self, response):
        locs = _LOC_RE.findall(response.text)
        logger.info(f"auchan_fr: shard={response.url} urls={len(locs)}")
        for url in locs:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        if response.status != 200:
            return
        text = response.text

        price_m = _PRICE_RE.search(text)
        title_m = _OG_TITLE_RE.search(text)
        if not price_m or not title_m:
            # Most commonly a discontinued PDP ("plus dans la gamme") --
            # no price meta at all. Not a price observation; skip.
            return

        name = ihtml.unescape(title_m.group(1)).strip()
        price = price_m.group(1).strip()
        if not name or not price:
            return

        currency_m = _CURRENCY_RE.search(text)
        currency = currency_m.group(1).strip() if currency_m else self.currency

        category = None
        cat_m = _CATEGORY_RE.search(text)
        if cat_m:
            try:
                cat_dict = json.loads("{" + cat_m.group(1) + "}")
            except ValueError:
                cat_dict = {}
            levels = [
                cat_dict.get(f"level{n}")
                for n in range(1, 6)
                if cat_dict.get(f"level{n}")
            ]
            category = " > ".join(levels) if levels else None

        id_m = _PRODUCT_ID_RE.search(response.url)
        product_id = id_m.group(1) if id_m else None

        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "price": price,
            "currency": currency,
            "category": category,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
