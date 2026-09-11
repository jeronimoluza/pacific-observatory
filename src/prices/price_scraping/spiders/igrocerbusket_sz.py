"""iGrocer Busket (Eswatini) -- https://igrocerbusket.store.link/.

Online grocery-delivery shop for Mbabane/Ezulwini, built on the "store.link"
storefront SaaS (Tailwind/Radix React app, server-rendered). The ENTIRE
catalog is embedded in the single homepage response -- no pagination, no
per-product PDP route found, no "load more" / infinite-scroll API calls in
the markup. Tier 1A, no WAF, plain `requests` returns 200.

Enumerability: measured 2026-09-11 -- 128 `product-card` blocks on the
homepage, 128 distinct product-card-title-text values, all 128 carrying a
`product-price-regular` value. No evidence of a truncated/paginated view
(no "load more" text, no client-side fetch endpoint referenced) -- treated
as total-count-confirmed for this single fetch, same reasoning as
busiquip_sz.py (one static complete data source, not a paginated listing).

Catalog: FMCG groceries -- cereals (Kellogg's, Bokomo), pasta (Fattis n
Monis, Sunny), rusks, oats, and more categories below the fold (the
category-menu carousel scrolled through cereals/pasta in the sample; the
full catalog spans the site's declared "household groceries" assortment).
Wide catalog, coicop_codes left unset for the classifier.

CURRENCY FLAG: prices render with the "R" (Rand) symbol, not the "E"
(Emalangeni/SZL) symbol used by other Eswatini sources in this repo (e.g.
sheshasd_sz, busiquip_sz). SZL is pegged 1:1 to ZAR and both circulate as
legal tender in Eswatini, so this is plausibly a South-African-sourced
price template rather than a currency error -- recorded here as ZAR
exactly as displayed (reading the payload, not assuming from the .shop
TLD), per the onboarding brief's instruction to flag rather than silently
normalize a non-default currency symbol. Downstream can treat SZL/ZAR as
at-par if that assumption is confirmed later.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_TITLE_RE = re.compile(r'product-card-title-text[^>]*title="([^"]+)"')
_PRICE_RE = re.compile(r'product-price-regular[^>]*>([^<]+)<')
_PRICE_NUM_RE = re.compile(r"([0-9][0-9,]*(?:[.,][0-9]{2})?)")


class IgrocerbusketSzSpider(scrapy.Spider):
    name = "igrocerbusket_sz"
    allowed_domains = ["igrocerbusket.store.link", "store.link"]
    currency = "ZAR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request(
            "https://igrocerbusket.store.link/",
            callback=self.parse_home,
        )

    def parse_home(self, response):
        cards = response.text.split('class="product-card group')[1:]
        seen: set[str] = set()
        for idx, card in enumerate(cards):
            m_name = _TITLE_RE.search(card)
            m_price = _PRICE_RE.search(card)
            if not m_name or not m_price:
                continue
            name = m_name.group(1).replace("&#x27;", "'").strip()
            price_raw = m_price.group(1).strip()
            m_num = _PRICE_NUM_RE.search(price_raw)
            if not m_num or not name:
                continue
            price = m_num.group(1).replace(",", ".")
            try:
                if float(price) <= 0:
                    continue
            except ValueError:
                continue
            url = f"https://igrocerbusket.store.link/#product-{idx}-{name[:30]}"
            if url in seen:
                continue
            seen.add(url)
            yield {
                "product_id": str(idx),
                "product_name": name[:500],
                "category": None,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
