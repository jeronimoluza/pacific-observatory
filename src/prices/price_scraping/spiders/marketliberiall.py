"""Maittes / MarketLiberiAll -- https://marketliberiall.com/ (canonical host
https://maittes.com)

Liberian online marketplace. Its storefront is a Next.js app whose product
grid is client-rendered -- /products server-renders 3 dollar figures, none of
them a catalog, which is what the earlier "needs API exploration" triage was
seeing. The route that works is the one its own robots.txt points at:

    Allow: /feeds/google-merchant.xml

    GET /feeds/google-merchant.xml  ->  application/rss+xml, a Google Merchant
    product feed. Measured 2026-09-12: 20 <item> entries, each with
    <title>, <g:price>, <g:availability>, <g:brand> (the seller) and a
    <link> permalink. Structured, no selectors, no JS.

CURRENCY: **LRD**, and this is the point of the source. `<g:price>` carries an
explicit currency token -- "5500.00 LRD" -- so unlike almost every other
Liberian storefront (which quote bare "$" and are dollarized), this one is
priced in Liberian dollars and says so machine-readably. The spider reads the
currency from the feed per item and never assumes; the class attribute is only
a fallback. Sample: "NPK Fertilizer 50kg Farm Sack", LRD 5500.00, seller
"Kollie Provision Shop".

CATALOG SIZE recorded deliberately: 20 items. Small, but real local goods
(farm inputs, provisions) priced in local currency, and it clears the >=5-row
gate comfortably. A future run seeing ~20 rows should read that as the feed's
real size, not a truncated parse. The feed is also the only view we have --
there is no paging parameter on it.

channel: marketplace -- the sellers are third parties ("Kollie Provision
Shop"), which is the population enrich/census.py excludes from the corpus
census. Tagged honestly.

Page family parsed: API (the RSS feed). The emitted url is the item's own
<link> permalink and is never fetched.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_FEED = "https://marketliberiall.com/feeds/google-merchant.xml"
# "5500.00 LRD" / "12.50 USD"
_PRICE_RE = re.compile(r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*([A-Z]{3})")


class MarketliberiallSpider(scrapy.Spider):
    name = "marketliberiall"
    allowed_domains = ["marketliberiall.com", "maittes.com"]
    currency = "LRD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request(_FEED, callback=self.parse_feed)

    def parse_feed(self, response):
        response.selector.remove_namespaces()
        items = response.xpath("//item")
        self.logger.info(f"{self.name}: {len(items)} items in merchant feed")
        for item in items:
            name = item.xpath("./title/text()").get()
            # after remove_namespaces() both <g:price> and <g:shipping><g:price>
            # collapse to "price"; the item-level one is the direct child
            price_text = item.xpath("./price/text()").get()
            if not name or not price_text:
                continue
            m = _PRICE_RE.search(price_text)
            if not m:
                continue
            price = m.group(1).replace(",", "")
            try:
                if float(price) <= 0:
                    continue
            except ValueError:
                continue
            yield {
                "product_id": item.xpath("./id/text()").get(),
                "product_name": name.strip()[:500],
                "price": price,
                "currency": m.group(2) or self.currency,
                "category": None,
                "url": item.xpath("./link/text()").get() or _FEED,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
