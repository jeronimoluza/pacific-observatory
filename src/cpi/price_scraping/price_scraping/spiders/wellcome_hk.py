"""
[STUB] Spider for Wellcome (Hong Kong) - https://www.wellcome.com.hk/

Strategy (to implement):
  - Nuxt.js (Vue SSR). Category listing pages are 16KB SPA shells (client-side
    rendered), so URL discovery probably needs Playwright on category pages.
  - Product detail pages are full SSR (~951KB) and embed schema.org `Product`
    JSON-LD with `price` and `priceCurrency` — plain HTTP fetch is enough once
    you have the URL list.
  - Product URL pattern: /en/wellcome/p/<name>/i/<id>.html
  - Wellcome and Mannings are both DFI Retail Group — possible shared backend.

Currently INACTIVE — needs (1) Playwright category sweep to enumerate URLs,
(2) plain-HTTP fetcher with schema.org JSON-LD parser (mirror of carrefour_tw).
"""

import scrapy


class WellcomeHkSpider(scrapy.Spider):
    name = "wellcome_hk"
    allowed_domains = ["www.wellcome.com.hk"]
    country = "hong_kong"
    currency = "HKD"
    language = "en"
    active = False

    def start_requests(self):
        return iter(())
