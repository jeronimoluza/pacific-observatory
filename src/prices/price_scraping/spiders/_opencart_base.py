"""
Shared base class for OpenCart storefront spiders (server-rendered category
HTML). Two category-URL conventions are seen across this wave:

- Classic OpenCart: `index.php?route=product/category&path=<id[_<id>...]>`,
  with the nav exposing the full parent/child id hierarchy (Blejeseshkoj).
  `parse_nav()` regex-scans a nav/menu page for every `path=` value, keeps
  only the leaves (paths that are not a prefix of a longer path, so parent
  categories that just re-list their children's products aren't double
  walked), and requests each leaf category with `limit=<LIMIT>` to collapse
  pagination where the install accepts it.
- SEO-rewritten clean URLs with no `route=`/`path=` at all (Ogi Market,
  big.ly, Carkeells): category entry points are just plain paths and must be
  supplied explicitly per-source via `CATEGORY_URLS`, since there is no
  generic way to tell a category slug from a product slug in that shape.

Product-card markup differs by theme (the two "Journal"-family stores here
use `.caption .name a` / `.price .price-new|.price-normal`; others use
`h4.protitle a` or `.content h4 a` and a plain `.price` block), so name/price
extraction tries several selectors in order and takes the first hit rather
than hard-coding one theme's shape. `product_id` prefers the numeric
`product_id=` query param when present, then a trailing `-<digits>` in the
URL, else falls back to the last path segment (clean-SEO stores have no
numeric id at all).

Underscored filename -- Scrapy's SpiderLoader skips classes without `name`.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

PATH_RE = re.compile(r"path=([0-9_]+)")
PRICE_NUM_RE = re.compile(r"\d[\d\s.,]*\d|\d")

NAME_SELECTORS = (
    "div.caption div.name a",
    "h4.protitle a",
    "div.content h4 a",
    "div.caption h4 a",
)
PRICE_SELECTORS = (
    ".price-new::text",
    ".price-normal::text",
    ".price-special::text",
    ".price ::text",
)


def normalize_price(raw: str) -> str | None:
    """Locale-aware price cleaner: strips currency symbols/letters, then
    decides whether a lone separator is decimal or thousands based on the
    digit-group length trailing it, and resolves comma+dot combinations by
    treating whichever separator occurs last as the decimal point."""
    if not raw:
        return None
    m = PRICE_NUM_RE.search(raw)
    if not m:
        return None
    s = re.sub(r"\s", "", m.group(0))
    has_comma, has_dot = "," in s, "." in s
    if has_comma and has_dot:
        if s.rindex(",") > s.rindex("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_comma:
        last = s.split(",")[-1]
        s = (
            s.replace(",", ".")
            if s.count(",") == 1 and len(last) in (1, 2)
            else s.replace(",", "")
        )
    elif has_dot:
        last = s.split(".")[-1]
        if not (s.count(".") == 1 and len(last) in (1, 2)):
            s = s.replace(".", "")
    try:
        float(s)
    except ValueError:
        return None
    return s


class OpencartBaseSpider(scrapy.Spider):
    # Subclasses MUST set: name, allowed_domains, currency, language, and
    # either CATEGORY_URLS (clean-SEO stores) or NAV_URL (classic route= /
    # path= stores, hierarchy auto-discovered from this page).
    name = None
    CATEGORY_URLS: tuple[str, ...] = ()
    NAV_URL: str = ""
    LIMIT = 100
    MAX_PAGES = 60

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        if self.NAV_URL:
            yield scrapy.Request(self.NAV_URL, callback=self.parse_nav)
        for url in self.CATEGORY_URLS:
            yield scrapy.Request(
                url, callback=self.parse_category, meta={"page": 1, "cat_url": url}
            )

    def parse_nav(self, response):
        paths = sorted(set(PATH_RE.findall(response.text)))
        leaves = [
            p for p in paths if not any(o != p and o.startswith(p + "_") for o in paths)
        ]
        base = response.url.split("index.php")[0] + "index.php"
        logger.info(f"{self.name}: {len(paths)} category paths, {len(leaves)} leaves")
        for p in leaves:
            url = f"{base}?route=product/category&path={p}&limit={self.LIMIT}"
            yield scrapy.Request(
                url, callback=self.parse_category, meta={"page": 1, "cat_url": url}
            )

    def parse_category(self, response):
        cards = self._product_cards(response)
        page = response.meta["page"]
        n = 0
        for card in cards:
            item = self._item(card, response)
            if item:
                n += 1
                yield item
        logger.info(
            f"{self.name}: {response.url} page={page} cards={len(cards)} items={n}"
        )

        cat_url = response.meta["cat_url"]
        if cards and page < self.MAX_PAGES:
            nxt = page + 1
            sep = "&" if "?" in cat_url else "?"
            yield scrapy.Request(
                f"{cat_url}{sep}page={nxt}",
                callback=self.parse_category,
                meta={"page": nxt, "cat_url": cat_url},
            )

    def _product_cards(self, response):
        cards = response.css("div.product-thumb")
        if cards:
            return cards
        return response.css("div.product-layout")

    def _item(self, card, response):
        name, url = None, None
        for sel in NAME_SELECTORS:
            a = card.css(sel)
            text = a.css("::text").get()
            if text and text.strip():
                name = text.strip()
                url = a.css("::attr(href)").get()
                break
        if not name:
            return None

        price_text = None
        for sel in PRICE_SELECTORS:
            val = card.css(sel).get()
            if val and val.strip():
                price_text = val
                break
        price = normalize_price(price_text) if price_text else None
        if not price:
            return None

        full_url = urljoin(response.url, url) if url else response.url
        product_id = self._product_id(full_url)

        return {
            "product_id": product_id,
            "product_name": name[:500],
            "category": self._category_label(response),
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": full_url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def _product_id(self, url: str) -> str:
        m = re.search(r"[?&]product_id=(\d+)", url)
        if m:
            return m.group(1)
        m = re.search(r"/product/([^/?]+)", url)
        if m:
            return m.group(1)
        m = re.search(r"-(\d+)$", url.split("?")[0].rstrip("/"))
        if m:
            return m.group(1)
        return url.rstrip("/").rsplit("/", 1)[-1]

    def _category_label(self, response):
        h1 = response.css("h1::text").get()
        if h1 and h1.strip():
            return h1.strip()
        m = re.search(r"path=([0-9_]+)", response.url)
        if m:
            return m.group(1)
        return response.meta.get("cat_url", response.url).rstrip("/").rsplit("/", 1)[-1]
