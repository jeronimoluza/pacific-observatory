"""
[STUB] Spider for Lotus's (Thailand) - https://www.lotuss.com/en/

Strategy (to implement):
  - Market leader by far in Thailand (~49% grocery share).
  - Next.js SPA with `__NEXT_DATA__` present but empty pageProps on both
    category and product pages. Sitemap returns minimal HTML. Direct
    `/api/...` attempts return 404. No schema.org data in product pages.
  - Playwright is required. Product data appears only after JS hydration.

Currently INACTIVE — needs Playwright-based pipeline; selectors TBD via
DevTools inspection of a hydrated product page.
"""

import scrapy


class LotussThSpider(scrapy.Spider):
    name = "lotuss_th"
    allowed_domains = ["www.lotuss.com"]
    country = "thailand"
    currency = "THB"
    language = "en"
    active = False

    def start_requests(self):
        return iter(())
