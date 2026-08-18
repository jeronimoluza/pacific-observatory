"""
Spider for Kaufland Romania weekly offers —
https://www.kaufland.ro/oferte/oferte-saptamanale/saptamana-curenta.html.

Kaufland.ro has no online grocery store (AEM/Adobe corporate site only,
confirmed via robots.txt/.sitemap.xml walk on 2026-08-06 -- purely
"sortiment/enciclopedia-alimentelor" editorial content plus store locator,
no shop). The weekly-offers ("oferte-saptamanale") circular page, however,
embeds the full current-week promo catalog as a JS object literal assigned
inline in a <script> tag: a `"offerData":{"cycles":[{"categories":[{...,
"offers":[{"offerId":...,"title":...,"price":...,"unit":...}]}]}]}` blob.

Re-verified live 2026-08-06: GET /oferte/oferte-saptamanale/saptamana-curenta.html
-> 301 -> /oferte/prezentare-generala-oferte.html?kloffer-week=current -> 200,
1.58MB, offerData block parses to 446 offers across the current week's
categories. Sample: 'Varza alba Romania' RON 1.49 (kg, discount 40%),
'Lamai' RON 7.99 (kg). Real, varied, local products with plausible prices.

This is promo/circular data (current week's discounted items), not a full
catalog -- narrower than a supermarket's whole assortment but still a
legitimate real-price feed, refreshed weekly.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_START_URL = "https://www.kaufland.ro/oferte/oferte-saptamanale/saptamana-curenta.html"


def _extract_json_object(text: str, key: str):
    marker = f'"{key}"'
    idx = text.find(marker)
    if idx == -1:
        return None
    start = text.find("{", idx)
    if start == -1:
        return None
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    else:
        return None
    try:
        return json.loads(text[start : i + 1])
    except ValueError:
        return None


class KauflandRoSpider(scrapy.Spider):
    name = "kaufland_ro"
    allowed_domains = ["kaufland.ro"]
    currency = "RON"
    language = "ro"

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
        offer_data = _extract_json_object(response.text, "offerData")
        if not offer_data:
            logger.warning(f"kaufland_ro: no offerData block at {response.url}")
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0
        for cycle in offer_data.get("cycles") or []:
            for cat in cycle.get("categories") or []:
                cat_name = cat.get("displayName") or cat.get("name") or ""
                for offer in cat.get("offers") or []:
                    offer_id = offer.get("offerId")
                    title = str(offer.get("title") or "").strip()
                    price = offer.get("price")
                    if not offer_id or not title or price is None:
                        continue
                    unit = offer.get("unit") or ""
                    product_name = f"{title} ({unit})" if unit else title
                    count += 1
                    yield {
                        "product_id": str(offer_id),
                        "product_name": product_name[:500],
                        "category": cat_name,
                        "price": str(price),
                        "currency": self.currency,
                        "available": True,
                        "url": f"{response.url}#{offer_id}",
                        "language": self.language,
                        "scraped_at_utc": scraped_at,
                    }
        logger.info(f"kaufland_ro: emitted {count} offers")
