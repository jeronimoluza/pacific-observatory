# Spider Templates

Three patterns for the `src/prices/price_scraping/spiders/` directory. Pick the one that matches the tier from SKILL.md Phase 3.

## Pattern A — Tier 1A: HTML/CSS, plain Scrapy

For server-rendered sites where the PDP HTML carries name + price in the raw response (no JS execution needed). Uses `CrawlSpider` + a shared selector registry. Mirror `src/prices/price_scraping/spiders/mh_online.py` or `rbpatel.py` exactly.

```python
"""
Spider for <Site Name> (<Country>) - <DOMAIN>
"""

import logging

from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class <ClassName>Spider(CrawlSpider):
    name = "<source_key>"
    allowed_domains = ["<DOMAIN>"]
    start_urls = ["<LISTING_URL_1>", "<LISTING_URL_2>"]
    currency = "<ISO_CCY>"

    SELECTORS = get_selectors("<source_key>")

    rules = (
        Rule(
            LinkExtractor(
                allow=r"<PRODUCT_URL_REGEX>",
                deny=r"(cart|checkout|account|login|search|<SITE_NON_PRODUCT_PATHS>)",
            ),
            callback="parse_product",
            follow=True,
        ),
    )

    def parse_product(self, response):
        extractor = SelectorExtractor(response, logger)
        product_name = extractor.extract("product_name", self.SELECTORS["product_name"])
        price = extractor.extract("price", self.SELECTORS["price"])
        category = extractor.extract(
            "category", self.SELECTORS.get("category", []), method="getall"
        )
        product_id = extractor.extract(
            "product_id", self.SELECTORS.get("product_id", [])
        )

        if product_name and price:
            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "currency": self.currency,
                "category": " > ".join(category) if category else None,
                "url": response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
            logger.info(f"Scraped product: {product_name}")
        else:
            logger.warning(f"Could not extract product data from {response.url}")
```

Then add a new entry to `src/prices/price_scraping/selectors.py` `SPIDER_SELECTORS` dict:

```python
"<source_key>": {
    "product_name": [
        "<most-specific-selector>::text",
        "meta[property='og:title']::attr(content)",
        "h1::text",  # last-resort fallback
    ],
    "price": [
        "<site-specific-price-selector>::text",
        "meta[property='product:price:amount']::attr(content)",
    ],
    "category": [
        "<breadcrumb-selector>::text",
    ],
    "product_id": [
        "meta[property='product:retailer_item_id']::attr(content)",
        "span.sku::text",
    ],
},
```

**Important LinkExtractor tips** (each one came from a real bug):

- `allow=r"\.html$"` is too broad on multilingual sites — it catches every `.html` URL including blog articles. Use a 2-segment path pattern instead: `r"/[a-z0-9\-]+/[a-z0-9\-]+\.html$"`.
- Add the site's *local-language* non-product path prefixes to `deny` — e.g. `/bai-viet/` (Vietnamese: articles), `/benh/` (Vietnamese: diseases), `/khuyen-mai` (promotions). A blanket `deny` of English `(login|cart|checkout)` doesn't catch these.
- For WooCommerce sites, deny `add-to-cart` URLs — those are `/shop/?add-to-cart=<id>` link clicks that LinkExtractor follows as new pages.

## Pattern B — Tier 2: Playwright listing-card extraction

For SPAs where the listing renders product cards with name + price inline after JS hydration. Uses `scrapy.Spider` (not CrawlSpider) so each Request can carry Playwright meta. Mirror `src/prices/price_scraping/spiders/fairprice.py`. No PDP visits — extract everything from the listing.

```python
"""
Spider for <Site Name>.
Listing-card extraction with Playwright. The listing page renders product
cards with name + price inline; no PDP visits required.
"""

import logging
import re

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)


class <ClassName>Spider(scrapy.Spider):
    name = "<source_key>"
    allowed_domains = ["<DOMAIN_1>", "<DOMAIN_2>"]
    currency = "<ISO_CCY>"

    START_URLS = [
        "<LISTING_URL_1>",
        "<LISTING_URL_2>",
    ]

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
    }

    PRICE_RE = re.compile(r"[\d,]+")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_urls: set[str] = set()

    def start_requests(self):
        for url in self.START_URLS:
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={
                    "playwright": True,
                    "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 6000),
                        PageMethod("evaluate",
                                   "window.scrollTo(0, document.body.scrollHeight / 2)"),
                        PageMethod("wait_for_timeout", 2000),
                        PageMethod("evaluate",
                                   "window.scrollTo(0, document.body.scrollHeight)"),
                        PageMethod("wait_for_timeout", 2000),
                    ],
                },
            )

    def parse_listing(self, response):
        cards = response.css("<CARD_CONTAINER_SELECTOR>")
        logger.info(f"<source_key>: found {len(cards)} product cards")
        for card in cards:
            href = card.css("a::attr(href)").get()
            if not href:
                continue
            url = response.urljoin(href)
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)

            # IMPORTANT ordering: image alt is the most stable name source.
            # Anchor `title` attribute often holds badge text ("sale", "new") that
            # steals priority — put it last or omit.
            name = (
                card.css("<IMG_SELECTOR_WITH_PRODUCT_CLASS>::attr(alt)").get()
                or card.css("img::attr(alt)").get()
                or card.css(".product-title::text, .product-name::text").get()
            )
            price_text = card.css("<PRICE_SELECTOR>::text").get() or ""
            price = None
            if price_text:
                m = self.PRICE_RE.search(price_text.strip())
                if m:
                    price = m.group(0)

            if not name or not price:
                continue

            yield {
                "product_id": None,  # often not on listing cards
                "product_name": name.strip(),
                "price": price,
                "currency": self.currency,
                "category": None,
                "url": url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
```

**Important Playwright tips**:

- `playwright_page_methods` runs *after* `goto`. The `wait_for_timeout` is a hard millisecond sleep — it's the only reliable wait for SPA hydration. Don't use `wait_until="networkidle"` — many SPAs keep WebSocket / analytics connections open and never go idle.
- Two scrolls (halfway → end) trigger lazy-loaded sections that scroll-based hydration uses. One scroll is often not enough.
- `custom_settings.CONCURRENT_REQUESTS: 1` is intentional. The global Playwright pool is capped (chromium tabs are expensive); running 4 spiders in parallel each with concurrency 1 is more reliable than 1 spider with concurrency 4.

**Reference: `fairprice.py` vs this template.** The existing `src/prices/price_scraping/spiders/fairprice.py` is a working Playwright listing-card spider you can read for context — but **don't copy its name-extraction order verbatim**. fairprice keeps `card.css("a::attr(title)").get()` as a fallback in `_parse_product_card`, and that selector regularly steals the product name when there's a discount/sale-overlay anchor in the card. This template's ordering (img.product alt → img alt → text-class → title last/omitted) is what you should follow.

**Multi-anchor cards.** Some sites render two `<a>` elements inside each card pointing at the same PDP — one wraps the image, one wraps the product-name text. A bare `card.css("a::attr(href)").get()` picks the first one (image-wrap), so `href` works; but a bare `card.css("a::attr(title)").get()` or first-anchor text extraction picks up the *image* anchor's title attribute, which is often empty or the file name. When you see this structure, pick the name-bearing anchor explicitly: `card.css("a.product-name::text, a.product-link::text").get()`, or iterate `card.css("a")` and choose the one whose visible text is longer than 8 characters (a heuristic but reliable — a "sale" badge anchor is always short).

### Variant: Tier 2 + PDP follow

Some Tier 2 sites need a follow-up PDP fetch (e.g. listing has URL + name but not price). Then yield Requests from `parse_listing` instead of items:

```python
yield scrapy.Request(
    pdp_url,
    callback=self.parse_product,
    meta={
        "playwright": True,
        "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
        "playwright_page_methods": [PageMethod("wait_for_timeout", 4000)],
        "product_id": pid,
    },
)
```

And in `parse_product`, prefer `meta[property='og:title']::attr(content)` and `meta[property='og:description']::attr(content)` — many SPAs render these meta tags reliably even when the body is half-hydrated. 11Street's og:description carries the full price ("강아지용품>사료>일반식사료, 가격 : 39,800원") which can be regex-extracted.

## Pattern C — Tier 1B: JSON API spider

For sites where you've sniffed an internal API endpoint that works without auth (or only requires Origin/Referer). No Playwright. Fastest, cleanest, and most stable when available. Mirror `src/prices/price_scraping/spiders/winmart.py`.

```python
"""
Spider for <Site Name>.

Uses the internal JSON API at <API_BASE> directly — bypasses the SPA front-end.
No Playwright required.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)


class <ClassName>Spider(scrapy.Spider):
    name = "<source_key>"
    allowed_domains = ["<API_HOSTNAME>"]
    currency = "<ISO_CCY>"

    # Site-specific path params (e.g. category slugs, store codes) live as class constants
    # so they're easy to find and adjust.
    CATEGORIES = ["<cat-slug-1>", "<cat-slug-2>"]
    PAGES_PER_CATEGORY = 1
    PAGE_SIZE = 20

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
    }

    def start_requests(self):
        headers = {
            "Accept": "application/json",
            "Origin": "<HTTPS_SITE_ORIGIN>",
            "Referer": "<HTTPS_SITE_ORIGIN>/",
        }
        for slug in self.CATEGORIES:
            for page in range(1, self.PAGES_PER_CATEGORY + 1):
                url = (
                    "<API_URL_TEMPLATE_WITH_PARAMS>"
                    f"&pageNumber={page}&pageSize={self.PAGE_SIZE}"
                    f"&slug={slug}"
                )
                yield scrapy.Request(
                    url,
                    headers=headers,
                    callback=self.parse_category,
                    meta={"slug": slug, "page": page},
                )

    def parse_category(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"JSON decode failed for {response.url}")
            return
        items = (payload.get("data") or {}).get("items") or []
        logger.info(
            f"<source_key>: slug={response.meta.get('slug')} "
            f"page={response.meta.get('page')} items={len(items)}"
        )
        for it in items:
            yield {
                "product_id": it.get("<ID_FIELD>"),
                "product_name": it.get("<NAME_FIELD>"),
                "price": it.get("<SALE_PRICE_FIELD>") or it.get("<PRICE_FIELD>"),
                "currency": self.currency,
                "category": it.get("<CATEGORY_FIELD>"),
                "url": f"<SITE_BASE>/{it.get('<SLUG_FIELD>')}" if it.get("<SLUG_FIELD>") else None,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
```

**Important API spider tips**:

- Set `ROBOTSTXT_OBEY: False` — API hosts often have aggressive robots.txt that disallows all crawlers, even though the API is publicly callable.
- Set Origin + Referer to match the site's actual origin. Some APIs reject requests without these (returning 429 or 403 even when no auth is required).
- Test the curl call from outside Scrapy first. If `curl -H 'Origin: ...' -H 'Referer: ...' '<url>'` returns 200 JSON, the spider will work. If it returns 401/429/403, the API needs auth — abandon and try Pattern B (Playwright).

## Shared-pipeline traps that silently delete rows

Four traps live in shared code, not in your spider. All four have cost a real
spider most or all of its output, and none of them raises an error you would
notice — you just get fewer rows than the site has. Check these before blaming
the site.

### `item["url"]` is the dedup key — never reuse one URL across products

`pipelines.py`'s `DuplicationPipeline` hashes `item["url"]` and drops repeats. So
a spider that parses ten products off one listing page and stamps the *listing
page's* URL on all ten keeps **one** of them.

Measured twice in one campaign:

- `willys_se`'s first draft emitted the category URL for every product and lost
  roughly **80%** of its items before anyone noticed the count was low.
- `talabat_eg` parses multi-item pages and had to append a per-item suffix for
  the same reason.

Always emit a genuinely per-product URL. If the API gives you a product id or
slug but no URL, build the canonical PDP URL from it (`asda_uk` derives one from
the `CIN` field and verified it against the live page's `og:title`) — do not fall
back to a constant.

**And do not "fix" a missing URL with `None`.** The same pipeline does
`item.get("url", "").encode()`, whose default applies only when the key is
**absent**, so a present-but-`None` url raises. The two obvious workarounds are
both wrong: `None` crashes the pipeline, a constant string collapses the whole
catalog to one row.

### `CustomUserAgentMiddleware` overwrites every User-Agent, and `settings.USER_AGENT` is dead

`price_scraping/middlewares.py`'s `CustomUserAgentMiddleware` unconditionally
rewrites the UA on every request. And `settings.USER_AGENT` is a **dead-letter
setting repo-wide**, because Scrapy's own `UserAgentMiddleware` (the thing that
would read it) is already disabled.

So if your source needs a specific UA — Googlebot-style SEO dynamic rendering, or
a UA that must match your TLS fingerprint — setting `custom_settings["USER_AGENT"]`
does nothing at all. Disable the middleware for your spider and set the header on
each `Request` explicitly:

```python
custom_settings = {
    "DOWNLOADER_MIDDLEWARES": {
        "price_scraping.middlewares.CustomUserAgentMiddleware": None,
    },
}
```

`plus_nl` ships this way (it needs a Googlebot UA to trigger OutSystems' SEO
rendering into real JSON-LD); `realestate_co_nz` established the pattern.

Note the mirror-image trap for Playwright: Scrapy's `USER_AGENT` does not reach a
browser context either. scrapy-playwright needs
`PLAYWRIGHT_CONTEXTS = {"default": {"user_agent": ...}}`.

### A UA override can also be the thing that *unblocks* a site — or backfires

Two hosts (`margaarou.com`, `lynia-shop.com`) 403 on `curl_cffi` across several
profiles AND on headless Playwright, and open on the first navigation once the
browser context UA is overridden to a plain Chrome string. A bare headless 403 is
no more evidence of a WAF than a bare-curl 403 is.

But it is not a general trick: on `ah.nl` and `ah.be`, spoofing Googlebot — which
worked on `plus_nl` — makes Akamai **blackhole the connection** instead. Try it,
measure it, and record which way it went.

### `_woo_sitemap_base` and `_woo_base` edge cases

- `parse_sitemap` misclassifies a child sitemap when the `<loc>` URL carries a
  query string after `.xml` (bennet.com's shape). `bennet_it` overrides
  `parse_sitemap` locally to work around it.
- `_woo_row_from_product_node` prefers `offers.url`, which on some tenants is
  **site-relative** — so those rows carry a relative `url`. Since `url` is the
  dedup key, resolve it against the page URL rather than emitting it raw.

## YAML manifest template

For all three patterns. Place at `src/prices/configs/<region>/<subregion>/<country>/<source>.yaml`:

```yaml
spider: <source_key>
language: <ISO_639_1>
# Optional fields:
# active: false           # disable a spider that's intentionally broken
# notes: >                # free-text gotchas for future maintainers
#   Uses internal JSON API. Re-probe selectors if site theme changes.
```

Do NOT add `region`, `subregion`, `country`, or `source` keys — they are derived from the file's path by `core.config.parse_config_path()`. Duplicating them is silently ignored at best and breaks the loader at worst.
