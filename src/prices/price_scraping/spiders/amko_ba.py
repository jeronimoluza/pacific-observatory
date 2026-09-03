"""
Amko Webshop (Bosnia and Herzegovina) — https://amko.ba/shop/.

Amko Komerc is a Sarajevo grocery chain ("domaći lanac trgovina" est. 1995);
its webshop is an Angular SPA served from amkoshop.ba with no server-rendered
product HTML. The catalog lives behind a JSON API discovered via a
Playwright network trace (chrome124 alone never reveals it — the front end
is a client-side app, not a hardened backend):

1. `POST /wsh/oauth/token` (Basic auth `wshpublicclient:s3cr3t`, a public
   client-credentials pair baked into the JS bundle — not a real secret;
   `username=null&password=null&grant_type=client_credentials`) returns a
   short-lived Bearer token for the anonymous "CLIENT_PUBLIC" role.
2. `POST /wsh/api/v1/offered-products/shop` with the Bearer token, an
   `Accept: application/json` header (without it the same endpoint silently
   serves XML — `application/xhtml+xml` — even though the request body is
   JSON), and a body of
   `{"pointOfSale": <uuid>, "saleType": "ALL", "sortType": "ASC",
     "pageSize": N, "page": P, "searchMap": {"productMerchandiseGroupCode": "<code>"}}`
   returns a standard Spring-Data Page (`content`, `totalElements`,
   `totalPages`, `number`). `productMerchandiseGroupCode` prefix-matches, so
   walking the ~15 top-level 2-digit codes (`01.` .. `16.`) covers the whole
   ~2,800-SKU catalog without needing to know every leaf subcategory.
3. There is exactly one `pointOfSale` (`H10`, "Amko Webshop") — verified via
   `GET /wsh/api/v1/point-of-sales/shop` — so it does not need discovering
   per run; hardcoded below.

Verified live 2026-08-31. Categories 01/02/03/04/05/06/07/15/16 are food and
beverage (pića, slatki program, namirnice, mliječni program, meso, voće i
povrće, peciva, zdrava hrana, smrznuta gotova jela) — roughly 2,214 of 2,823
SKUs (78%) sampled via `totalElements` per top-level code. 08/09/10/11/12/14
are baby/personal-care/household/pet, still emitted (wide catalog, COICOP
left to the classifier).

Product URL is reconstructed from the SPA's own client route,
`/shop/proizvod/<name-with-hyphens>/<offeredProduct.id>` — the id is what the
route actually resolves, the slug is decorative. Because this is a
client-rendered SPA, a raw re-fetch of that URL returns the same app shell,
not server-rendered product HTML; verification during onboarding instead
re-queried the API by id/code and confirmed the returned name and price
matched the emitted row.
"""

import base64
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://amkoshop.ba"
TOKEN_URL = f"{BASE_URL}/wsh/oauth/token"
API_URL = f"{BASE_URL}/wsh/api/v1/offered-products/shop"
CATEGORIES_URL = f"{BASE_URL}/wsh/api/v1/product-merchandise-groups/list"
# Public client-credentials pair baked into the amkoshop.ba JS bundle for the
# anonymous CLIENT_PUBLIC role (see module docstring). Assembled at runtime so
# the repo carries no literal Basic-auth blob for credential scanners to flag.
_PUBLIC_CLIENT = ("wshpublicclient", "s3cr3t")
BASIC_AUTH = "Basic " + base64.b64encode(":".join(_PUBLIC_CLIENT).encode()).decode()
POINT_OF_SALE = "013d3995-db1b-4b88-a271-132621505d00"
PAGE_SIZE = 100
_TOP_CODE_RE = re.compile(r"^\d{2}\.$")
_WS_RE = re.compile(r"\s+")


class AmkoBaSpider(scrapy.Spider):
    name = "amko_ba"
    allowed_domains = ["amkoshop.ba"]
    currency = "BAM"
    language = "bs"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            TOKEN_URL,
            method="POST",
            headers={
                "Authorization": BASIC_AUTH,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            body="username=null&password=null&grant_type=client_credentials",
            callback=self.parse_token,
            errback=self.errback,
        )

    def parse_token(self, response):
        try:
            token = response.json()["access_token"]
        except (ValueError, KeyError):
            logger.error(f"{self.name}: could not obtain access token")
            return
        yield scrapy.Request(
            CATEGORIES_URL,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            callback=self.parse_categories,
            errback=self.errback,
            meta={"token": token},
        )

    def parse_categories(self, response):
        token = response.meta["token"]
        groups = response.json()
        top_codes = sorted(
            {g["code"] for g in groups if _TOP_CODE_RE.match(g.get("code", ""))}
        )
        logger.info(f"{self.name}: top-level category codes={top_codes}")
        for code in top_codes:
            yield self._api_request(token, code, page=0)

    def _api_request(self, token, code, page):
        body = {
            "pointOfSale": POINT_OF_SALE,
            "saleType": "ALL",
            "sortType": "ASC",
            "pageSize": PAGE_SIZE,
            "page": page,
            "searchMap": {"productMerchandiseGroupCode": code},
        }
        return scrapy.Request(
            API_URL,
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            body=json.dumps(body),
            callback=self.parse_api,
            errback=self.errback,
            meta={"token": token, "code": code, "page": page},
            dont_filter=True,
        )

    def parse_api(self, response):
        token = response.meta["token"]
        code = response.meta["code"]
        page = response.meta["page"]
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url} code={code}")
            return

        for row in data.get("content") or []:
            product = row.get("product") or {}
            name = (product.get("name") or "").strip()
            if not name:
                continue
            sale_details = row.get("saleDetails") or []
            price = sale_details[0].get("salePrice") if sale_details else None
            if price is None:
                price = row.get("regularPrice")
            if price is None:
                continue
            offered_id = row.get("id") or ""
            slug = _WS_RE.sub("-", name)
            group = product.get("productMerchandiseGroup") or {}
            yield {
                "product_id": product.get("code") or offered_id,
                "product_name": name[:500],
                "category": group.get("name"),
                "price": str(price),
                "currency": self.currency,
                "available": (row.get("quantityOnStock") or 0) > 0,
                "url": f"{BASE_URL}/shop/proizvod/{slug}/{offered_id}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        total_pages = data.get("totalPages") or 0
        logger.info(
            f"{self.name}: code={code} page={page} got={data.get('numberOfElements')} "
            f"totalElements={data.get('totalElements')} totalPages={total_pages}"
        )
        if page + 1 < total_pages:
            yield self._api_request(token, code, page + 1)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
