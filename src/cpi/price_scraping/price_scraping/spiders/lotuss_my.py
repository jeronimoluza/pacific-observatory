"""
[STUB] Spider for Lotus's (Malaysia) - https://www.lotuss.com.my/en/

Strategy (to implement):
  - Adobe Experience Manager (AEM) Franklin / Edge-Delivery SPA. All pages —
    category and product — return ~7-9KB JS shells. No schema.org data is
    embedded server-side.
  - The public sitemap (https://www.lotuss.com.my/en/sitemap.xml) lists
    13,636 product URLs at /en/product/{id}. Use this as a seed list rather
    than crawling categories blind.
  - Each product detail page must be rendered with Playwright (Chromium,
    `wait_until=networkidle`) before extracting price + name from the rendered
    DOM. Selectors TBD until first inspection — open one product page in
    Playwright and probe.

Currently INACTIVE (active=False) — needs Playwright-based product page
parsing implemented.
"""

import scrapy


class LotussMySpider(scrapy.Spider):
    name = "lotuss_my"
    allowed_domains = ["www.lotuss.com.my"]
    country = "malaysia"
    currency = "MYR"
    language = "en"
    active = False

    def start_requests(self):
        return iter(())
