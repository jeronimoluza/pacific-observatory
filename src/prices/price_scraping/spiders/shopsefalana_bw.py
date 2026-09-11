"""Sefalana Online Store (Botswana, nopCommerce) — https://shopsefalana.com/

Sefalana is Botswana's largest domestic food-retail group. This storefront
(NopStation.Theme.Arch theme on a stock nopCommerce install -- confirmed via
`/Plugins/NopStation.*` and `/Themes/Arch/` asset paths, no `meta
name="generator"` tag but the markup is otherwise identical to the
winners_mu.py nopCommerce pattern) is a genuine, very wide supermarket
catalogue: staple foods, rice, maize, wheat, sugar, oil, canned goods,
dairy, bakery, snacks, confectionery, tea/coffee, juices, carbonated and
energy drinks -- AND a full liquor/tobacco range (beers, brandy, ciders,
gin, liqueurs, rum, tequila, vodka, whiskey, wines, cigarettes, tobacco).
Single source with plausible coverage across most of COICOP divisions
01 and 02.

Server-rendered, no WAF: plain (non-impersonating) `requests` gets HTTP 200
on every path tested 2026-09-11 (homepage, `/dairy-4`, `/beers`).

Category discovery differs from winners_mu.py: this theme has no
`lastLevelCategory` marker. Categories are discovered from the homepage's
flat nav link list (`href="/<slug>"`, single path segment, nopCommerce
auto-appends a numeric suffix to disambiguate same-named slugs e.g.
`/dairy-4`, `/beers` has none). A denylist strips non-category chrome
(`/cart`, `/contactus`, `/customer/*`, `/Plugins`, `/Themes`, `/lib`,
`/loyalty`, `/order`, `/promotions`, `/privacy-notice`,
`/frequently-asked-questions`, `/conditions-of-use`, `/recipe-hut`,
`/motshelo-tradeshow`) plus the homepage's brand and single-product
carousel links (per the winners_mu.py docstring's warning, this theme also
mixes in single-product hrefs like `/gordons-gin-london-dry-1-x-750ml` and
brand pages like `/nivea`, `/simba`, `/gillette` -- these are harmless to
crawl as "categories" since they simply yield zero `product-item` matches,
but are pre-filtered here to save requests where recognisable).

Category display name is derived from the slug (strip nopCommerce's
trailing `-<digits>` suffix, replace dashes with spaces, title-case) since
no page carries a plain-text H1/breadcrumb in this theme's markup.

Listing: `<slug>?pagesize=75&pagenumber=N`, products in
`div.product-item[data-productid]` blocks, same shape as winners_mu.py.
Price is split across two spans -- `span.price.actual-price` ("P52", Pula
symbol prefix) and `span.price.actual-price-cents` ("99") -- concatenated
here into "52.99". Confirmed against `/dairy-4` and `/beers`: 20/20 items
priced on both pages sampled, all P-prefixed (BWP). No separate
machine-readable currency code was found; BWP fixed at spider level to
match countries.yaml and the storefront's own "P" display.

Enumerability: `/dairy-4` page1 vs page2 (`?pagenumber=2`) returned fully
disjoint `data-productid` sets (20 vs 20, zero overlap) -- genuinely
paginates. A page is followed to N+1 only while it returned a full
PAGE_SIZE batch.

Language: html lang not checked in detail, but product names and category
taxonomy are English-language (matches countries.yaml).
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://shopsefalana.com"
PAGE_SIZE = 75
MAX_PAGES = 40  # safety cap per category (3,000 SKUs)
MAX_CATEGORIES = 200  # safety cap on homepage nav slugs followed

_NAV_LINK_RE = re.compile(r'href="(/[a-zA-Z0-9_-]{2,60})"')

_DENYLIST = {
    "cart",
    "contactus",
    "conditions-of-use",
    "login",
    "register",
    "search",
    "newsletter",
    "sitemap",
    "wishlist",
    "compareproducts",
    "privacy-policy-and-cookie-declaration",
    "privacy-notice",
    "topic",
    "recentlyviewedproducts",
    "news",
    "blog",
    "about-us",
    "terms-of-service",
    "loyalty",
    "order",
    "promotions",
    "frequently-asked-questions",
    "recipe-hut",
    "motshelo-tradeshow",
    "birthday-specials",
}
_PREFIX_DENYLIST = ("customer", "cat-2", "Plugins", "Themes", "lib")

# Single-product carousel links / brand pages mixed into the homepage nav,
# not real category listing pages -- harmless if crawled (zero product-item
# matches) but pre-filtered to save requests.
_BRAND_OR_PRODUCT_RE = re.compile(
    r"^(gillette|nivea|old-spice|oral-b|simba|rajah|nutriday|maq|clover)$"
    r"|-\d+-x-\d+(ml|g|kg|l)$"
)

_PRODUCT_RE = re.compile(
    r'<div class="product-item" data-productid="(?P<pid>\d+)">.*?'
    r'<h2 class="product-title">\s*<a href="(?P<url>[^"]+)">(?P<name>[^<]+)</a>\s*</h2>.*?'
    r'<span class="price actual-price">\s*P\s*(?P<rand>\d[\d,]*)\s*</span>\s*'
    r'<span class="price actual-price-cents">\s*(?P<cents>\d{2})\s*</span>',
    re.S,
)


def _category_title(slug: str) -> str:
    slug = re.sub(r"-\d+$", "", slug.strip("/"))
    return slug.replace("-", " ").title()


def _clean_price(rand: str, cents: str) -> str:
    return f"{rand.replace(',', '')}.{cents}"


class ShopSefalanaBwSpider(scrapy.Spider):
    name = "shopsefalana_bw"
    allowed_domains = ["shopsefalana.com"]
    currency = "BWP"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(f"{BASE_URL}/", callback=self.parse_home)

    def parse_home(self, response):
        slugs: set[str] = set()
        for m in _NAV_LINK_RE.finditer(response.text):
            slug = m.group(1).lstrip("/")
            if not slug or slug in _DENYLIST:
                continue
            if any(slug.startswith(p) for p in _PREFIX_DENYLIST):
                continue
            if _BRAND_OR_PRODUCT_RE.search(slug):
                continue
            slugs.add(slug)
        slugs = sorted(slugs)[:MAX_CATEGORIES]
        logger.info(f"{self.name}: {len(slugs)} candidate category slugs")
        for slug in slugs:
            yield scrapy.Request(
                f"{BASE_URL}/{slug}?pagesize={PAGE_SIZE}&pagenumber=1",
                callback=self.parse_category,
                meta={"category": _category_title(slug), "page": 1, "slug": slug},
                dont_filter=True,
            )

    def parse_category(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        slug = response.meta["slug"]
        matches = list(_PRODUCT_RE.finditer(response.text))
        logger.info(
            f"{self.name}: category={category} page={page} count={len(matches)}"
        )
        for m in matches:
            yield {
                "product_id": m.group("pid"),
                "product_name": html.unescape(m.group("name")).strip(),
                "category": category,
                "price": _clean_price(m.group("rand"), m.group("cents")),
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(m.group("url")),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        if len(matches) >= PAGE_SIZE and page < MAX_PAGES:
            next_page = page + 1
            yield scrapy.Request(
                f"{BASE_URL}/{slug}?pagesize={PAGE_SIZE}&pagenumber={next_page}",
                callback=self.parse_category,
                meta={"category": category, "page": next_page, "slug": slug},
                dont_filter=True,
            )
