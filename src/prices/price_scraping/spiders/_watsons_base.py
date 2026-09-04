"""
Shared base class for Watsons Asia/EAP spiders.

Watsons runs the same Angular SSR storefront across at least 7 EAP countries
(SG, HK, TH, MY, PH, ID, TW). All sit behind AkamaiGHost and serve identical
PDP markup:
  <wtc-product-price-summary>...<div class="display-price">
    <span>{CURRENCY_SYMBOL}</span><span class="price">9.24</span>
  </div>...

Curl_cffi with chrome120 TLS impersonation (via scrapy-impersonate) bypasses
the WAF. Each country has the same /sitemap.xml -> /sitemap_prd_{lang}_NN.xml
discovery pattern, with TW being the only outlier (no `en` sitemap, only zh_TW).

Subclasses override seven attributes (name/allowed_domains/currency/language/
SITEMAP_INDEX/SITEMAP_FILTER/PRICE_SYMBOL); everything else is inherited.

Underscored filename — Scrapy's SpiderLoader skips classes without `name`.
"""

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import unquote

import scrapy

from ..archived import (
    iter_jsonld_nodes,
    normalize_price,
    row_from_meta,
    rows_from_jsonld,
)

logger = logging.getLogger(__name__)

LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
ID_RE = re.compile(r"/p/(BP_\d+)")


def _is_product_group(node: dict) -> bool:
    t = node.get("@type")
    if isinstance(t, list):
        return any(str(x).lower() == "productgroup" for x in t)
    return str(t).lower() == "productgroup"


def _rows_from_product_group(html_text: str, url: str) -> list[dict]:
    """Rows from schema.org ``ProductGroup`` nodes -- Watsons-specific.

    Most Watsons PDPs emit a plain ``Product`` node that `rows_from_jsonld`
    already handles. A minority (multi-variant color/shade pages, verified
    on watsons.co.th archived samples) emit ``ProductGroup`` instead, with
    the price on the group's ``AggregateOffer`` rather than per-variant --
    a shape `rows_from_jsonld` does not recognize since it only matches
    ``@type: Product``. One row per group (using the group price), not per
    variant, since `hasVariant` entries carry no price of their own.
    """
    rows: list[dict] = []
    for node in iter_jsonld_nodes(html_text):
        if not _is_product_group(node):
            continue
        name = node.get("name")
        if not name:
            continue
        offers = node.get("offers") or {}
        price = normalize_price(offers.get("price") or offers.get("lowPrice"))
        if not price:
            continue
        row = {
            "product_name": str(name).strip()[:500],
            "price": price,
            "url": node.get("url") or url,
        }
        group_id = node.get("productGroupID") or node.get("sku")
        if group_id:
            row["product_id"] = str(group_id)
        currency = offers.get("priceCurrency")
        if currency:
            row["currency"] = str(currency)
        category = node.get("category")
        if isinstance(category, dict):
            category = category.get("name")
        if category:
            row["category"] = str(category)
        availability = offers.get("availability")
        if availability:
            row["available"] = "instock" in str(availability).lower()
        rows.append(row)
    return rows


class WatsonsBaseSpider(scrapy.Spider):
    # Subclasses MUST set: name, allowed_domains, currency, language,
    # SITEMAP_INDEX, SITEMAP_FILTER, PRICE_SYMBOL.
    name = None
    IMPERSONATE_PROFILE = "chrome120"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        # Every Watsons storefront sits behind ONE AS Watson edge that
        # identifies us by client IP, so these numbers are a whole-fleet
        # budget, not a per-site one. `throttle_group: aswatson` keeps
        # siblings from running concurrently; do not raise these on top of
        # that without a fresh measurement.
        #
        # 2026-08-27: raising these to 8/16/0.25s was tried and REVERTED
        # unvalidated. On 2026-08-26 the edge 403-banned this IP across every
        # storefront (homepage included) after ~29k requests from 7 parallel
        # children plus a 2h solo crawl. The ban arrived with NO 429 warning
        # -- the solo crawl saw zero rate-limit responses for two hours first.
        # Volume over a rolling window is the trigger, so throughput tuning is
        # the wrong lever here: going faster only reaches the cap sooner.
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 4,
    }

    SITEMAP_INDEX: str = ""
    SITEMAP_FILTER: str = "sitemap_prd_en"
    PRICE_SYMBOL: str = ""

    async def start(self):
        yield scrapy.Request(
            self.SITEMAP_INDEX,
            callback=self.parse_index,
            meta={"impersonate": self.IMPERSONATE_PROFILE},
        )

    def parse_index(self, response):
        for loc in LOC_RE.findall(response.text):
            if self.SITEMAP_FILTER in loc:
                yield scrapy.Request(
                    loc,
                    callback=self.parse_product_sitemap,
                    meta={"impersonate": self.IMPERSONATE_PROFILE},
                )

    def parse_product_sitemap(self, response):
        urls = LOC_RE.findall(response.text)
        logger.info(f"{self.name}: {len(urls)} product URLs in {response.url}")
        for url in urls:
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_product(self, response):
        body = response.text

        name = self._extract_name(response, body)
        if not name:
            return

        price = self._extract_price(response, body)
        if not price:
            return

        m = ID_RE.search(response.url)
        product_id = m.group(1) if m else response.url

        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": self._extract_category(body),
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def _extract_name(self, response, body: str) -> str | None:
        og = response.xpath('//meta[@property="og:title"]/@content').get()
        if og:
            return og.strip()
        h1 = response.xpath("//h1//text()").get()
        if h1:
            return h1.strip()
        m = re.search(r"<title>([^<|]+)", body)
        return m.group(1).strip() if m else None

    def _extract_price(self, response, body: str) -> str | None:
        sale = response.xpath(
            '//div[contains(@class, "display-price") '
            'and not(contains(@class, "recommended"))]'
            '//span[contains(concat(" ", normalize-space(@class), " "), " price ")]/text()'
        ).get()
        if sale:
            sale = sale.strip()
            if re.match(r"^\d+(?:[\.,]\d+)?$", sale):
                return (
                    sale.replace(",", ".") if "," in sale and "." not in sale else sale
                )
        m = re.search(r'"lowPrice":\s*([0-9]+(?:\.[0-9]+)?)', body)
        if m:
            return m.group(1)
        m = re.search(r'"price":\s*([0-9]+(?:\.[0-9]+)?)', body)
        if m:
            return m.group(1)
        if self.PRICE_SYMBOL:
            pat = re.escape(self.PRICE_SYMBOL) + r"\s*([0-9]+(?:[,.][0-9]+)?)"
            m = re.search(pat, body)
            if m:
                return (
                    m.group(1).replace(",", ".")
                    if "," in m.group(1) and "." not in m.group(1)
                    else m.group(1)
                )
        return None

    def _extract_category(self, body: str) -> str | None:
        for m in re.finditer(
            r"<script[^>]*application/ld\+json[^>]*>\s*(\[.*?\]|\{.*?\})\s*</script>",
            body,
            re.DOTALL,
        ):
            try:
                data = json.loads(m.group(1))
                if isinstance(data, list):
                    data = next(
                        (
                            d
                            for d in data
                            if isinstance(d, dict)
                            and d.get("@type") == "BreadcrumbList"
                        ),
                        None,
                    )
                if isinstance(data, dict) and data.get("@type") == "BreadcrumbList":
                    items = data.get("itemListElement", [])
                    names = [
                        (i.get("item") or {}).get("name") or i.get("name")
                        for i in items
                        if isinstance(i, dict)
                    ]
                    names = [unquote(n) for n in names if n and n != "Home"]
                    if names:
                        return " > ".join(names[:3])
            except Exception:
                continue
        return None

    @classmethod
    def parse_html(cls, html: str, url: str):
        """Parse one archived Watsons PDP into row dicts.

        The live spider reads server-rendered PDP HTML directly (there is no
        separate JSON API), so archived Wayback/CC snapshots are the *same*
        page shape the live parser already targets -- but the shared
        `rows_from_jsonld` tier in archived.py is tried first since it is
        cheaper and, per onboarding measurement across 7 countries (HK/TW/
        ID/MY/PH/SG/TH, 42 archived pages, 2026-08-18), resolved 35/42 pages
        (83%) outright via the plain schema.org ``Product`` node every PDP
        carries. The remaining misses split two ways: a `ProductGroup`
        fallback (this module's `_rows_from_product_group`) recovers
        multi-variant pages that emit ``@type: ProductGroup`` with an
        ``AggregateOffer`` instead of a plain ``Product`` node (2/42, all on
        watsons.co.th); the other 3/42 (HK/TW/ID) are Angular SSR shells
        Common Crawl captured before client-side hydration populated any
        product data at all -- `cx-state` shows empty `product`/`details`
        entities, so no text-level parser can recover them. Does NOT stamp
        `scraped_at_utc` -- the caller sets it to the snapshot time.
        """
        rows = rows_from_jsonld(html, url) or _rows_from_product_group(html, url)
        if not rows:
            meta_row = row_from_meta(html, url)
            rows = [meta_row] if meta_row else []
        for row in rows:
            # Each Watsons subclass is one country's storefront in one fixed
            # currency (see module docstring) -- never trust the archived
            # page's own priceCurrency over it. watsons_ph shipped 446 rows
            # tagged TWD (2018-2020) because a stale/cross-region snapshot's
            # JSON-LD said so; PHP is what the site has ever charged.
            row["currency"] = cls.currency
            row.setdefault("language", cls.language)
            yield row
