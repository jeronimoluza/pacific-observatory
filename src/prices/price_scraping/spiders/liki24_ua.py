"""
Liki24 Ukraine -- https://liki24.com/. Online pharmacy marketplace.

OpenCart-derived backend (PHPSESSID cookies, an `index.php?route=...`
endpoint that is accepted but ignored) served through a bespoke Angular
Universal SSR frontend (`/vnext/` build, buildId-tagged), not a classic
Journal-theme install. Category pages at
`https://liki24.com/category/<id>/` are still server-rendered with real
prices in the initial HTML -- confirmed live 2026-09-10 with plain
`curl_cffi` (`impersonate="chrome124"`), no Playwright needed at
collection time. Playwright WAS needed to discover this: bare Playwright
(no stealth) trips a real Cloudflare block ("Sorry, you have been
blocked") that curl_cffi's TLS impersonation does not, and even with
`--disable-blink-features=AutomationControlled` several of the site's own
same-origin `/vnext/api/*` XHR calls (including the true product-list API,
`/vnext/api/catalogue/<id>/products`) 403 under Cloudflare while the
server-rendered page itself is untouched -- so this spider reads the SSR
HTML rather than any `/api/` endpoint.

Card markup is entirely different from the classic OpenCart themes
`_opencart_base.py`'s module-level `NAME_SELECTORS`/`PRICE_SELECTORS` were
written against, so neither matches out of the box (`_item()` would return
None for every card): products sit in `<lk-product-card-md>` custom
elements, the name anchor is `a.name` directly (not nested under
`div.caption`/`h4.protitle` as the base's selector list assumes), and the
charged price is always `.price .final-price` -- a sibling `.old-price`
appears only when discounted, so the base's own last-resort fallback
selector (`.price ::text`, first text node under `.price`) would silently
grab the pre-discount price on ~15% of cards. `_product_cards()`/`_item()`
are overridden below to match this theme; `_opencart_base.py` itself is
untouched, and `parse_category()`'s pagination loop, `MAX_PAGES` cap, and
"fresh empty-set" trap-avoidance are inherited unmodified.

Enumerability confirmed live 2026-09-10: `/category/8000051/` (Лекарства
для сердца и сосудов, cardiovascular meds) page=1 vs `?page=2` -> 20
distinct product slugs each, 0 overlap -> DISTINCT. The site's
`sitemap_ru_categories_1.xml` lists 1005 base `/category/<id>/` pages, so
the catalog is large; low-numbered ids (~8000001-8000030) are department
hubs with no direct products (subcategory tiles only), while ids sampled
in the 8000040-8000068 range each carried 20 direct product cards on page
1. Only 5 category ids are seeded here -- CATEGORY_URLS is not exhaustive
-- because the backend rate-limits aggressive bursts (HTTP 429 after
~5-6 rapid unthrottled requests from one IP); the inherited
`DOWNLOAD_DELAY=2.0` / `CONCURRENT_REQUESTS_PER_DOMAIN=1` politeness
settings are load-bearing here, not just courtesy.

Currency UAH confirmed via the response's own `Set-Cookie: currency=UAH`
and the "грн" (hryvnia) suffix on every displayed price. Pharmacy catalog
spans many COICOP classes (Rx and OTC medicines, supplements, cosmetics,
baby care) -- channel: pharmacy, coicop_codes left unset per the skill's
narrowness rule so the classifier assigns a leaf per product.
"""

from datetime import datetime, timezone

from price_scraping.spiders._opencart_base import OpencartBaseSpider, normalize_price


class Liki24UaSpider(OpencartBaseSpider):
    name = "liki24_ua"
    allowed_domains = ["liki24.com"]
    currency = "UAH"
    language = "ru"
    CATEGORY_URLS = (
        "https://liki24.com/category/8000040/",
        "https://liki24.com/category/8000047/",
        "https://liki24.com/category/8000054/",
        "https://liki24.com/category/8000061/",
        "https://liki24.com/category/8000068/",
    )
    MAX_PAGES = 20

    def _product_cards(self, response):
        return response.css("lk-product-card-md")

    def _item(self, card, response):
        a = card.css("a.name")
        name = a.css("::text").get()
        if not name or not name.strip():
            return None
        name = name.strip()

        price_text = card.css(".price .final-price::text").get()
        price = normalize_price(price_text) if price_text else None
        if not price:
            return None

        href = a.css("::attr(href)").get()
        full_url = response.urljoin(href) if href else response.url

        return {
            "product_id": full_url.rstrip("/").rsplit("/", 1)[-1],
            "product_name": name[:500],
            "category": self._category_label(response),
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": full_url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
