"""
Alko — https://www.alko.fi/ (Finnish state alcohol retail monopoly).

Next.js app; the product grid is not server-rendered (a plain fetch of
/fi/tuotteet has no product markup, only client bundles). Found the real
data source via a Playwright network trace: POST /api/search/product?lang=fi
is an Azure Cognitive Search index (`@odata.count` signature) fronting the
complete catalogue -- 11,223 products, no auth, plain JSON body
`{"top": N, "skip": N}`. Verified live 2026-09-06 with curl_cffi
impersonate=chrome124: 200, full product records (id, name, price EUR,
volume, mainGroupName/productGroupName categories, ABV, country). One
Playwright hit surfaced a transient Azure Front Door WAF JS challenge
(`.azwaf/jsc/...`, an `afd_azwaf_tok` retry) on the very first request of
that session, but every direct curl_cffi request in this probe (all 5
impersonation profiles on the page, plus the API POST) returned a clean
200 with no challenge -- not a real block, just occasional edge-side
bot-scoring noise.

price is already a plain EUR float (administered/regulated retail price,
matches the AI_NOTES' "Finnish COICOP 2.1 benchmark" framing) -- no
minor-unit or symbol-parsing risk. category is the Finnish
mainGroupName joined with productGroupName (e.g. "viinit / valkoviinit").
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.alko.fi"
API_URL = f"{BASE_URL}/api/search/product?lang=fi"
PAGE_SIZE = 100


class AlkoFiSpider(scrapy.Spider):
    name = "alko_fi"
    allowed_domains = ["alko.fi"]
    currency = "EUR"
    language = "fi"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield self._make_request(skip=0)

    def _make_request(self, skip: int) -> scrapy.Request:
        return scrapy.Request(
            API_URL,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Referer": f"{BASE_URL}/fi/tuotteet",
            },
            body=json.dumps({"top": PAGE_SIZE, "skip": skip}),
            callback=self.parse_page,
            meta={"skip": skip},
            errback=self.errback,
        )

    def parse_page(self, response):
        skip = response.meta["skip"]
        try:
            data = json.loads(response.text)
        except ValueError:
            logger.warning(f"{self.name}: bad JSON at skip={skip}")
            return

        total = data.get("@odata.count", 0)
        rows = data.get("value") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        found = 0

        for it in rows:
            product_id = it.get("id")
            name = it.get("name")
            price = it.get("price")
            if not product_id or not name or price is None:
                continue

            main_group = ", ".join(it.get("mainGroupName") or [])
            product_group = ", ".join(it.get("productGroupName") or [])
            category = " / ".join(filter(None, [main_group, product_group]))

            found += 1
            yield {
                "product_id": str(product_id),
                "product_name": str(name).strip()[:500],
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": f"{BASE_URL}/fi/tuotteet/{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(
            f"{self.name}: skip={skip} rows={len(rows)} yielded={found} total={total}"
        )

        next_skip = skip + PAGE_SIZE
        if rows and next_skip < total:
            yield self._make_request(skip=next_skip)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
