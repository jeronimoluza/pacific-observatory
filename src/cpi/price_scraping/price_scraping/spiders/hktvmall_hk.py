"""
[STUB] Spider for HKTVmall (Hong Kong) - https://www.hktvmall.com/

Strategy (to implement):
  - Largest HK e-commerce platform (~600K+ items, ~35% of HK consumers).
  - Pure JavaScript SPA: all curl requests return a 3,839-byte JS shell. No
    public API found (OCC/SAP Hybris-style paths return 404).
  - Server-side rendering not confirmed — assume full Playwright is required
    for both category sweeps and product detail pages.
  - 345 Wayback pages exist — historical depth is good once selectors are
    nailed down.

Currently INACTIVE — needs full Playwright-based pipeline (category enumeration
+ product page extraction) and selector discovery via DevTools.
"""

import scrapy


class HktvmallHkSpider(scrapy.Spider):
    name = "hktvmall_hk"
    allowed_domains = ["www.hktvmall.com"]
    country = "hong_kong"
    currency = "HKD"
    language = "en"
    active = False

    def start_requests(self):
        return iter(())
