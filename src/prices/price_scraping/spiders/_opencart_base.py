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
from typing import Iterator
from urllib.parse import urljoin

import scrapy

from ..archived import row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)

# Archived-page-only fallback: covers themes with neither JSON-LD nor
# OpenGraph price meta (e.g. big.ly's X-Cart-flavoured OpenCart theme, which
# has none of NAME_SELECTORS/PRICE_SELECTORS' classes but does carry a plain
# `.pro-price` node next to a single page `<h1>`).
_ARCHIVE_PDP_PRICE_SELECTORS = (
    ".price-new::text",
    ".price-normal::text",
    ".price-special::text",
    ".pro-price::text",
    ".price ::text",
)


def _archive_product_id(url: str) -> str:
    """Same convention as `OpencartBaseSpider._product_id` (below), reimplemented
    as a free function so the archived-page path needs no spider instance."""
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

    # ------------------------------------------------------------------
    # Crawl backfiller (prices/backfill.py's parse_html hook). Live scrape
    # (parse_category/_item, above) walks server-rendered category listing
    # pages; archives hold whatever page type Common Crawl happened to
    # capture -- product-detail pages, category listing pages, or (rarely)
    # neither. Tries, in order: the shared schema.org/OpenGraph tiers (most
    # OpenCart themes emit one or the other); the SAME product-card
    # selectors `_item`/`_product_cards` use, for when the captured page is
    # a category listing rather than a PDP (yields one row per card); and a
    # bespoke single-product fallback (`<h1>` + a widened price-selector
    # list) for themes with neither -- confirmed needed on big.ly, whose
    # archived PDPs have no JSON-LD/meta price tags but a plain
    # `<h1>name</h1>` + `.pro-price` pair.
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(cls, html_text: str, url: str) -> Iterator[dict]:
        """Parse one archived OpenCart page (product-detail or category listing).

        Pure/stateless: no Scrapy Response, no network, no class state.
        Yields 0 or more rows; yields nothing when neither a product nor a
        product listing can be found. Does NOT stamp `scraped_at_utc` -- the
        backfiller stamps the snapshot time itself.
        """
        rows = rows_from_jsonld(html_text, url)
        if not rows:
            row = row_from_meta(html_text, url)
            rows = [row] if row else []
        if rows:
            for row in rows:
                row.setdefault("currency", cls.currency)
                row.setdefault("language", cls.language)
                yield row
            return

        sel = scrapy.Selector(text=html_text)
        cards = sel.css("div.product-thumb") or sel.css("div.product-layout")
        if cards:
            yield from cls._archived_listing_items(cards, url)
            return

        item = cls._archived_pdp_item(sel, url)
        if item:
            yield item

    @classmethod
    def _archived_listing_items(cls, cards, base_url: str) -> Iterator[dict]:
        for card in cards:
            name, href = None, None
            for csel in NAME_SELECTORS:
                a = card.css(csel)
                text = a.css("::text").get()
                if text and text.strip():
                    name = text.strip()
                    href = a.css("::attr(href)").get()
                    break
            if not name:
                continue
            price_text = None
            for psel in PRICE_SELECTORS:
                val = card.css(psel).get()
                if val and val.strip():
                    price_text = val
                    break
            price = normalize_price(price_text) if price_text else None
            if not price:
                continue
            full_url = urljoin(base_url, href) if href else base_url
            yield {
                "product_id": _archive_product_id(full_url),
                "product_name": name[:500],
                "price": price,
                "currency": cls.currency,
                "available": True,
                "url": full_url,
                "language": cls.language,
            }

    @classmethod
    def _archived_pdp_item(cls, sel, url: str) -> dict | None:
        name = sel.css("h1::text").get()
        name = name.strip() if name else None
        if not name:
            return None
        price_text = None
        for psel in _ARCHIVE_PDP_PRICE_SELECTORS:
            val = sel.css(psel).get()
            if val and val.strip():
                price_text = val
                break
        price = normalize_price(price_text) if price_text else None
        if not price:
            return None
        return {
            "product_id": _archive_product_id(url),
            "product_name": name[:500],
            "price": price,
            "currency": cls.currency,
            "available": True,
            "url": url,
            "language": cls.language,
        }
