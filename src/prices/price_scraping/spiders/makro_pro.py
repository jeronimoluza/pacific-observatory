"""
Spider for Makro PRO (Thailand) - https://www.makro.pro

#1 Thai grocery/hypermarket e-commerce. The JS storefront (Next.js) reads a
public Typesense-backed search proxy that returns the full catalog with no
auth. This spider POSTs an empty query to that proxy and paginates via `page`,
reading Thai product titles + THB prices directly from each hit document.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SEARCH_URL = (
    "https://search.maknet.siammakro.cloud/search/api/v1/indexes/products/search"
)
_PDP_BASE = "https://www.makro.pro/th/p/"
_MAX_PAGES = 3000


class MakroProSpider(scrapy.Spider):
    name = "makro_pro"
    allowed_domains = ["siammakro.cloud", "makro.pro"]
    currency = "THB"
    language = "th"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_MAX_DELAY": 30.0,
        "RETRY_TIMES": 6,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 408],
    }

    _HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://www.makro.pro",
        "Referer": "https://www.makro.pro/",
    }

    def start_requests(self):
        yield self._page_request(1)

    def _page_request(self, page):
        body = json.dumps({"q": "", "page": page})
        return scrapy.Request(
            _SEARCH_URL,
            method="POST",
            body=body,
            headers=self._HEADERS,
            callback=self.parse_page,
            meta={"page": page},
            dont_filter=True,
        )

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("makro_pro: non-JSON response p%d", page)
            return

        hits = payload.get("hits") or []
        logger.info(
            "makro_pro: page=%d hits=%d found=%s", page, len(hits), payload.get("found")
        )
        if not hits:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for h in hits:
            doc = h.get("document") or {}
            name = doc.get("title") or doc.get("titleEn")
            price = doc.get("displayPrice")
            if not name or price is None:
                continue
            makro_id = doc.get("makroId")
            product_id = doc.get("sku") or (str(makro_id) if makro_id else None)
            url = f"{_PDP_BASE}{makro_id}" if makro_id else None
            yield {
                "product_id": product_id,
                "product_name": name,
                "price": str(price),
                "currency": doc.get("priceUnit") or self.currency,
                "category": doc.get("deepestCategory") or None,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if page < _MAX_PAGES:
            yield self._page_request(page + 1)
