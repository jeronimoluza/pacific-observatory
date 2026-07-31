"""
Spider for New World Fiji (Fiji) - newworld.com.fj.

19-store IGA-affiliated chain. The storefront is an Angular SPA backed by a
Vendure GraphQL API at https://api.newworld.com.fj/shop-api. Vendure's search
plugin is disabled, so the catalogue is walked via the `products` query with
take/skip pagination. Pricing is per-store (channel-scoped): the `vendure-token`
header selects a store channel. We pin the Suva flagship (S0033 — NEWWORLD IGA
Suva, Greig St); without a valid store token the default channel returns no
price. Currency is FJD (confirmed via activeChannel). priceWithTax comes back as
an integer in thousandths of a dollar (the frontend divides by 1000), so
3500 -> FJD 3.50.

A variant with no price in the Suva channel makes Vendure's non-null
`priceWithTax` resolver throw, and GraphQL's non-null propagation nulls the whole
page's `data` (there is no nullable price field to select instead). Each error
carries the offending item's path index, so a poisoned window is recovered by
dropping exactly the reported unpriced item, keeping the clean left chunk, and
recursing on the right — rather than losing the ~4.5k good items that share
poisoned pages.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API = "https://api.newworld.com.fj/shop-api"
_STORE_TOKEN = "S0033"
_PAGE_SIZE = 100
_PRICE_SCALE = 1000
_MAX_PAGES = 400  # safety cap

_QUERY = (
    "query($take:Int!,$skip:Int!){"
    "products(options:{take:$take,skip:$skip}){"
    "totalItems items{id name slug "
    "variants{id sku priceWithTax currencyCode} "
    "collections{name}}}}"
)


class NewWorldFijiSpider(scrapy.Spider):
    name = "new_world_fiji"
    allowed_domains = ["api.newworld.com.fj"]
    currency = "FJD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.5,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 5,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 408],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._total_items = None
        self._dropped_unpriced = 0

    def _request(self, skip, take, is_page):
        body = json.dumps({"query": _QUERY, "variables": {"take": take, "skip": skip}})
        return scrapy.Request(
            _API,
            method="POST",
            body=body,
            callback=self.parse_page,
            errback=self.errback,
            meta={"skip": skip, "take": take, "is_page": is_page},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "vendure-token": _STORE_TOKEN,
            },
            dont_filter=True,
        )

    async def start(self):
        yield self._request(skip=0, take=_PAGE_SIZE, is_page=True)

    def _first_bad_index(self, errors):
        idxs = []
        for e in errors:
            path = e.get("path") or []
            if (
                len(path) >= 3
                and path[0] == "products"
                and path[1] == "items"
                and isinstance(path[2], int)
            ):
                idxs.append(path[2])
        return min(idxs) if idxs else None

    def parse_page(self, response):
        skip = response.meta["skip"]
        take = response.meta["take"]
        is_page = response.meta["is_page"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(
                "new_world_fiji: non-JSON response skip=%d take=%d", skip, take
            )
            return

        products = (payload.get("data") or {}).get("products")
        if products is not None and products.get("totalItems") is not None:
            self._total_items = products.get("totalItems")

        if products is not None and products.get("items") is not None:
            items = products.get("items") or []
            logger.info(
                "new_world_fiji skip=%d take=%d count=%d", skip, take, len(items)
            )
            yield from self._emit(items)
        else:
            errors = payload.get("errors") or []
            bad = self._first_bad_index(errors)
            if bad is None:
                logger.error(
                    "new_world_fiji: poisoned skip=%d take=%d no path index; "
                    "bisecting",
                    skip,
                    take,
                )
                if take <= 1:
                    self._dropped_unpriced += max(take, 0)
                else:
                    half = take // 2
                    yield self._request(skip, half, is_page=False)
                    yield self._request(skip + half, take - half, is_page=False)
            else:
                self._dropped_unpriced += 1
                logger.info(
                    "new_world_fiji: unpriced item abs=%d (skip=%d off=%d)",
                    skip + bad,
                    skip,
                    bad,
                )
                if bad > 0:
                    yield self._request(skip, bad, is_page=False)
                right_take = take - bad - 1
                if right_take > 0:
                    yield self._request(skip + bad + 1, right_take, is_page=False)

        if is_page:
            nxt = skip + _PAGE_SIZE
            total = self._total_items
            if (total is None or nxt < total) and (nxt // _PAGE_SIZE) < _MAX_PAGES:
                yield self._request(nxt, _PAGE_SIZE, is_page=True)

    def _emit(self, items):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in items:
            name = p.get("name")
            slug = p.get("slug")
            if not name:
                continue
            category = (
                " > ".join(
                    c.get("name")
                    for c in (p.get("collections") or [])
                    if isinstance(c, dict) and c.get("name")
                )
                or None
            )
            url = f"https://www.newworld.com.fj/product/{slug}" if slug else None
            for v in p.get("variants") or []:
                raw = v.get("priceWithTax")
                if raw is None:
                    continue
                try:
                    price = f"{int(raw) / _PRICE_SCALE:.2f}"
                except (TypeError, ValueError):
                    continue
                yield {
                    "product_id": str(v.get("id") or p.get("id")),
                    "product_name": name.strip(),
                    "price": price,
                    "currency": v.get("currencyCode") or self.currency,
                    "category": category,
                    "url": url,
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }

    def errback(self, failure):
        logger.error(
            "new_world_fiji: request failed %s — %r",
            failure.request.url,
            failure.value,
        )
