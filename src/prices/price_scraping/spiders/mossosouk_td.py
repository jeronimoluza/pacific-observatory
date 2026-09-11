"""Mossosouk.com (Chad) -- https://www.mossosouk.com/. Custom multi-vendor
marketplace (not Woo/Shopify/Presta/OpenCart -- no wp-json, no /products.json,
no /rest/V1). Confirmed genuinely N'Djamena-based: footer address "Rue 2038,
Route de la Corniche, N'Djamena-Tchad", phone +235 65 60 25 69 (+235 = Chad).

No product-listing API; PDPs carry clean RDFa/schema.org microdata instead:
`<h1 property="schema:name" content="...">`, `<... property="schema:price"
content="3000">`, `<div property="schema:priceCurrency" content="XAF">` --
confirmed XAF (not just displayed "FCFA" text) on huile-de-palme-rouge.

Enumerated via /sitemap.xml (a single flat file, 288 <loc> entries, ~288
distinct /product/ URLs, no sitemap index -- this covers the whole catalog)
rather than the ~45 /category/ pages, since PDP fetches are needed anyway for
the currency-bearing microdata and the site is small enough that a per-PDP
crawl is cheap. Category listing pages (e.g. /category/placard-alimentaire)
do NOT carry schema microdata and were confirmed to NOT paginate differently
between page 1 and an explicit ?page=2 -- the sitemap-driven PDP crawl sidesteps
that entirely.

Catalog is thin for food: of 288 total products, only ~24 sit under the
"Placard Alimentaire" (15: cooking oils, flours, spices, dried fruit, coffee
substitutes) and "Boisson" (9: herbal teas/infusions) categories -- the rest
is cosmetics, electronics, fashion, baby gear, agricultural tools. Scraped as
a wide marketplace (coicop_codes left unset) rather than narrowed to two
categories, matching the tchadcommerce_td precedent for this country.

Page family: PDP only (sitemap gives the URL list; category/listing pages are
never fetched).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy
from bs4 import BeautifulSoup


class MossosoukTdSpider(scrapy.Spider):
    name = "mossosouk_td"
    allowed_domains = ["mossosouk.com"]
    currency = "XAF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            "https://www.mossosouk.com/sitemap.xml",
            callback=self.parse_sitemap,
        )

    def parse_sitemap(self, response):
        urls = set(re.findall(r"<loc>(https://www\.mossosouk\.com/product/[^<]+)</loc>", response.text))
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        name_el = soup.select_one('[property="schema:name"]')
        price_el = soup.select_one('[property="schema:price"]')
        currency_el = soup.select_one('[property="schema:priceCurrency"]')
        if not name_el or not price_el:
            return
        name = name_el.get("content") or name_el.get_text(strip=True)
        price = price_el.get("content")
        if not name or not price:
            return
        try:
            if float(price) <= 0:
                return
        except (TypeError, ValueError):
            return
        currency = (currency_el.get("content") if currency_el else None) or self.currency

        crumbs = [
            a.get_text(strip=True)
            for a in soup.select(".ps-breadcrumb .breadcrumb li a")
        ]
        category = crumbs[-1] if crumbs else None

        product_id = response.url.rstrip("/").rsplit("/", 1)[-1]

        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category,
            "price": str(price),
            "currency": currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
