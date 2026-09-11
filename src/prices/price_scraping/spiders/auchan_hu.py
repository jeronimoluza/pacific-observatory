"""Auchan Hungary -- https://auchan.hu/ (storefront app at online.auchan.hu).

Not the same platform as any other Auchan banner built so far (RO=VTEX,
PT=SFCC, SN=PrestaShop, UA=Zakaz white-label) -- online.auchan.hu itself
serves a heavy client-rendered shell, but robots.txt on the marketing
domain points at a separate, fully server-rendered sitemap chain:
https://auchan.hu/sitemap.xml -> a <sitemapindex> of 3 product shards
(product-sitemap-0/1/2.xml, 20,000 + 20,000 + 10,258 = 50,258 <loc>
entries, verified live 2026-09-10) plus category/cms/content shards that
this base class also walks but that carry zero URLs matching
PRODUCT_URL_RE (categories use `.c-<id>`, products use `.p-<id>`).

Product URLs are plain HTML pages (`/shop/<slug>.p-<id>`) with a
schema.org Product JSON-LD block -- no impersonation or Playwright
needed, plain requests.get 200s. Verified 4 different PDPs across shard 0
and shard 1: '1x1 Vitamin Kalcium + Magnezium ...' HUF 2079, '1x1 Vitaday
Magnezium ...' HUF 1919, 'Sam Mills Pasta d'Oro Fusilli ...' HUF 955,
'Samia barbecue szosz ...' HUF 1699. Shard 0 and shard 1 are disjoint --
alphabetically partitioned by product-name slug (shard 0 starts at
"1-1-vitamin...", shard 1 at "sam-mills...").
"""

from __future__ import annotations

from ._woo_sitemap_base import WooSitemapBaseSpider


class AuchanHuSpider(WooSitemapBaseSpider):
    name = "auchan_hu"
    allowed_domains = ["auchan.hu"]
    SITEMAP_URL = "https://auchan.hu/sitemap.xml"
    PRODUCT_URL_RE = r"\.p-\d+$"
    currency = "HUF"
    language = "hu"
