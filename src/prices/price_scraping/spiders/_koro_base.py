"""
Shared base class for KoRo (Shopware 6) storefront spiders.

KoRo (koro.com / korodrogerie.de / koro-shop.{at,it,ch} / ...) is a Nuxt 3
frontend over a shared Shopware 6 backend at `bff.koro.com`, with one
Shopware "sales channel" per country. The Nuxt SSR payload embeds
`window.__NUXT__.config.public.localizedFrontendsContext.channels`, a list
of `{salesChannelCode, accessKey, domains, currency}` objects -- one per
country storefront, each with its own `sw-access-key`. That key is scoped to
its sales channel (a key from one storefront 403s / returns a different
catalog on a sibling channel of the same platform -- do not assume one key
works everywhere), so each subclass below carries its own key extracted from
its country's homepage HTML.

Catalog access is the standard Shopware 6 Store API, POST'd (not GET) with
the access key as a header:

    POST https://bff.koro.com/store-api/product
    sw-access-key: <channel's key>
    Content-Type: application/json
    body: {"limit": 100, "page": N, "total-count-mode": 1}

`total-count-mode: 1` is required to get an exact `total` in the response --
omitted, Shopware returns `total == len(elements)` for that page only, which
looks like a 1-page catalog and silently truncates the crawl. Pagination via
`page` (1-indexed); stop when `len(elements) < limit`.

Price is `calculatedPrice.unitPrice` (already resolved to the channel's
currency/tax context, not a shared EUR figure -- verified DKK/CHF channels
return locale-appropriate magnitudes, not blind EUR passthrough). Reference
unit price/size lives in `calculatedPrice.referencePrice` when present
(`purchaseUnit`, `referenceUnit`, `unitName`).

No canonical SEO path is present in the plain product listing (`seoUrls` is
null without an explicit association include), so this uses Shopware's
built-in non-SEO canonical detail route `/detail/{id}` as the product URL --
a real, resolvable PDP, and unique per product (avoids the DuplicationPipeline
url-collapse bug that bites spiders using a constant or missing per-product
URL).

Subclasses set: name, allowed_domains, currency, language, ACCESS_KEY,
DOMAIN (first domain from that channel's `domains` list, used to build the
product URL).

Underscored filename -- Scrapy's SpiderLoader skips classes without `name`.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Iterator

import scrapy

from ..archived import meta_tags, normalize_price, row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)

_API_URL = "https://bff.koro.com/store-api/product"
_LIMIT = 100


class KoroBaseSpider(scrapy.Spider):
    name = None
    ACCESS_KEY: str = ""
    DOMAIN: str = ""
    currency: str = ""
    language: str = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def _request(self, page: int):
        return scrapy.Request(
            _API_URL,
            method="POST",
            headers={
                "sw-access-key": self.ACCESS_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            body=json.dumps({"limit": _LIMIT, "page": page, "total-count-mode": 1}),
            callback=self.parse,
            meta={"page": page},
        )

    async def start(self):
        yield self._request(1)

    def parse(self, response):
        data = json.loads(response.text)
        elements = data.get("elements") or []
        page = response.meta["page"]
        n = 0
        for el in elements:
            item = self._item(el)
            if item:
                n += 1
                yield item
        logger.info(
            f"{self.name}: page={page} total={data.get('total')} "
            f"returned={len(elements)} items={n}"
        )
        if len(elements) == _LIMIT:
            yield self._request(page + 1)

    def _item(self, el):
        name = (el.get("translated") or {}).get("name") or el.get("name")
        product_id = el.get("productNumber") or el.get("id")
        price = (el.get("calculatedPrice") or {}).get("unitPrice")
        if not name or not product_id or price is None:
            return None
        return {
            "product_id": str(product_id),
            "product_name": name.strip()[:500],
            "category": None,
            "price": price,
            "currency": self.currency,
            "available": bool(el.get("available")),
            "url": f"https://{self.DOMAIN}/detail/{el.get('id')}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def parse_html(cls, html: str, url: str) -> Iterator[dict]:
        """Archived KoRo product-detail page (`/detail/<id>`) -> price rows.

        Measured on 25 archived pages across 5 country storefronts (AT, CH,
        ES, IT, SE): the shared schema.org JSON-LD tier alone carries 24/25
        -- every KoRo PDP embeds a single ``Product`` node with ``offers``.
        The one JSON-LD miss (a page rendered without the offer block) still
        has a match, since KoRo also stamps ``itemprop`` microdata meta tags
        (``price`` / ``pricecurrency``) that agree with JSON-LD to the cent
        everywhere both are present -- more reliable here than the generic
        OpenGraph fallback, whose ``product:price:amount`` reads a stale
        ``"0"`` on that same page (a real bug in that tag, not in the shared
        helper) and would silently zero the price.
        """
        rows = rows_from_jsonld(html, url)
        if rows:
            yield from rows
            return
        row = cls._koro_meta_row(html, url)
        if row:
            yield row

    @staticmethod
    def _koro_meta_row(html: str, url: str) -> dict | None:
        meta = meta_tags(html)
        price = normalize_price(meta.get("price"))
        name = meta.get("og:title") or meta.get("twitter:title")
        if price and name:
            row = {
                "product_name": name.strip()[:500],
                "price": price,
                "url": meta.get("og:url") or url,
            }
            currency = meta.get("pricecurrency")
            if currency:
                row["currency"] = currency
            return row
        return row_from_meta(html, url)
