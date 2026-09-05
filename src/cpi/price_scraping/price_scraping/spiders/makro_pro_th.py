"""
[STUB] Spider for Makro PRO (Thailand) - https://www.makro.pro/

Strategy (to implement):
  - #1 grocery e-commerce in Thailand by Euromonitor (~39.5% market share).
  - Next.js SPA (~2.4MB bundle); empty pageProps on product/category pages.
  - Strapi CMS for content (`strapi-cdn.mango-prod.siammakro.cloud`) — possibly
    a public Strapi REST endpoint exists. Worth probing before falling back to
    Playwright.
  - Product data appears client-side only.

Currently INACTIVE — needs (1) Strapi/REST API discovery via Playwright network
interception; (2) full Playwright fallback if no public API.

Note: distinct from existing `makro` spider, which targets Makro Cambodia
(makroclick.com).
"""

import scrapy


class MakroProThSpider(scrapy.Spider):
    name = "makro_pro_th"
    allowed_domains = ["www.makro.pro"]
    country = "thailand"
    currency = "THB"
    language = "en"
    active = False

    def start_requests(self):
        return iter(())
