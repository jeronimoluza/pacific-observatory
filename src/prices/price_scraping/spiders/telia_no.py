"""
Telia Norway mobile-subscription price list —
https://www.telia.no/privat/mobilabonnement.

Next.js SSR page. No pagination needed: the single listing page embeds a
schema.org ProductGroup JSON-LD-shaped object directly inside __NEXT_DATA__
(props.pageProps.productGroupSchema), one `hasVariant` entry per plan with
a clean Offer (sku/price/priceCurrency/availability). Verified live
2026-08-31: 11 plans, e.g. 'Telia X Start' sku TELIA_X_START_2026 -> NOK
499/mnd, InStock. Narrow single-class tariff source (mobile telephone
service plans, COICOP 08.2), not a retailer catalogue -- product_id is the
plan sku, category is fixed to the schema's "MobileTelephoneService".
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_START_URL = "https://www.telia.no/privat/mobilabonnement"
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>\s*(.*?)\s*</script>', re.DOTALL
)


class TeliaNoSpider(scrapy.Spider):
    name = "telia_no"
    allowed_domains = ["telia.no"]
    currency = "NOK"
    language = "no"
    start_urls = [_START_URL]

    def parse(self, response):
        match = _NEXT_DATA_RE.search(response.text)
        if not match:
            logger.warning("telia_no: __NEXT_DATA__ not found on %s", response.url)
            return

        try:
            data = json.loads(match.group(1))
        except (ValueError, TypeError):
            logger.warning("telia_no: __NEXT_DATA__ JSON parse failed")
            return

        page_props = data.get("props", {}).get("pageProps", {})
        product_group = page_props.get("productGroupSchema") or {}
        variants = product_group.get("hasVariant") or []
        scraped_at = datetime.now(timezone.utc).isoformat()

        for variant in variants:
            offers = variant.get("offers") or {}
            price = offers.get("price")
            sku = variant.get("sku")
            name = variant.get("name")
            if not sku or not name or price in (None, "", 0, "0"):
                continue
            # offers.url is identical for every plan on this single listing
            # page (the pipeline dedups on URL) -- use the variant's own
            # @id, which is unique per plan, instead.
            url = variant.get("@id") or f"{response.url}#{sku}"
            yield {
                "product_id": str(sku),
                "product_name": html.unescape(str(name)).strip()[:500],
                "category": variant.get("category") or product_group.get("category"),
                "price": str(price),
                "currency": offers.get("priceCurrency") or self.currency,
                "available": str(offers.get("availability", "")).endswith("InStock"),
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
