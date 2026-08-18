"""
Spider for ishopping.pk -- Pakistan online department store (Magento 2,
server-rendered Luma theme). robots.txt is open (only /admin_ao0fl6/ and
/lofmarketplace/ disallowed, no ClaudeBot/anthropic-ai entry).

curl_cffi impersonate=chrome124 clears cleanly with no challenge; plain
`requests` also 200s, so this spider does not impersonate.

Pagination gotcha (re-verified live 2026-08-17, contradicting an earlier
note on this exact domain): on the live category grid, `?p=N` is the real
Magento pager -- `/electronics?p=2` returns 150 fully different product
cards, and `/tv-s-and-entertainment/led-tv?p=2` (a 28-item, single-page
category) correctly returns an EMPTY grid, i.e. real out-of-range paging.
`?page=N` is the no-op here: `/electronics?page=1` and `?page=2` return
byte-for-byte the same first-page card order. `MagentoSSRBaseSpider`
already defaults `PAGE_PARAM = "p"`, which matches -- no override needed.

Category start URLs are a curated cross-department sample pulled from
`https://www.ishopping.pk/sitemap/sitemap-1-1.xml` (shallow, <=1-segment
paths only -- deeper sitemap entries are brand/PDP pages, not listings).
"""

from price_scraping.spiders._magento_base import MagentoSSRBaseSpider

_START_URLS = [
    "https://www.ishopping.pk/electronics",
    "https://www.ishopping.pk/mens-store",
    "https://www.ishopping.pk/women-s-store",
    "https://www.ishopping.pk/kids-store",
    "https://www.ishopping.pk/tv-s-and-entertainment",
    "https://www.ishopping.pk/computers",
    "https://www.ishopping.pk/tablets",
    "https://www.ishopping.pk/office-media",
    "https://www.ishopping.pk/health-beauty",
]


class IshoppingPkSpider(MagentoSSRBaseSpider):
    name = "ishopping_pk"
    allowed_domains = ["ishopping.pk"]
    currency = "PKR"
    language = "en"
    START_URLS = _START_URLS
