"""
Spider for Konzum (Croatia) — https://www.konzum.hr/.

Custom PHP/Symfony-style storefront (not Next.js/Vue despite round-1's platform
guess — re-verified live 2026-08-06, no __NEXT_DATA__/__NUXT__ marker present).
Most category/search routes (`/kategorije/<slug>`, `/api/categories`,
`/pretraga`, `/web/pretraga`, `/rezultati-pretrage`) 200 but all return an
identical ~172KB soft-404 shell with zero product markup — this app is a
client-rendered SPA for normal browsing.

The one confirmed-live SSR exception is the `/kreni-u-kupnju` landing page
("start shopping" — a static seasonal produce/promo page, `data-ga-list`
literally says "Statička stranica" = "Static page"). It server-renders real
product-impression tracking attributes directly in the markup:
`data-ga-id`/`data-ga-name`/`data-ga-price`/`data-ga-brand`/`data-ga-category`
on each `<article class="product-item product-default...">`, plus a
`<a class="link-to-product" href="/web/products/<slug>">` for the URL.
Verified: 13 real, varied products incl. 'Grožđe crno' (black grapes) 1,49 €,
'Vindon Pureće mljeveno meso 500 g' (turkey mince) 4,39 €, 'Barilla
Tjestenina fusilli 1 kg' 1,85 €.

SCOPE CAVEAT: only this one static page was reachable this pass — round 1's
"12,000+ products" estimate could not be reproduced; no other category route
rendered product markup without JS execution. Ships as a narrow, single-page
source; widening to the full catalog needs the SPA's underlying category API
(not found this pass — Playwright network-tab discovery would be the next
step, not in scope for a curl-only probe).
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.konzum.hr"
_START_URL = f"{_BASE}/kreni-u-kupnju"

_ARTICLE_RE = re.compile(r'<article class="product-item[^"]*">.*?</article>', re.S)
_CARD_RE = re.compile(
    r'data-ga-id="([^"]+)"\s*'
    r'data-ga-name="([^"]+)"\s*'
    r'data-ga-price="([^"]+)"\s*'
    r'data-ga-brand="([^"]*)"\s*'
    r'data-ga-category="([^"]*)"',
)
_URL_RE = re.compile(r'<a class="link-to-product" href="([^"]+)">')


class KonzumHrSpider(scrapy.Spider):
    name = "konzum_hr"
    allowed_domains = ["konzum.hr"]
    currency = "EUR"
    language = "hr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_START_URL, callback=self.parse_page)

    def parse_page(self, response):
        articles = _ARTICLE_RE.findall(response.text)
        logger.info(f"konzum_hr: articles={len(articles)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for block in articles:
            card = _CARD_RE.search(block)
            if not card:
                continue
            pid, name, price, brand, category = card.groups()
            url_match = _URL_RE.search(block)
            url = (
                f"{_BASE}{url_match.group(1)}"
                if url_match
                else f"{_BASE}/web/products#{pid}"
            )
            price_clean = price.replace("€", "").replace(",", ".").strip()
            yield {
                "product_id": pid,
                "product_name": html.unescape(name).strip()[:500],
                "category": (category or brand or "").strip("/"),
                "price": price_clean,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
