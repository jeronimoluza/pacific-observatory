"""
Shared base class for PrestaShop storefront spiders (server-rendered category
HTML; the /api/products webservice needs a key and 401s, so this walks the
public catalog instead).

Category discovery is generic: PrestaShop's clean-URL convention puts
categories at `/{lang/}{id}-{slug}` with no `.html` suffix, while product
URLs carry an extra category-slug segment and always end in `.html`
(`/fr/legumes/180-aubergine-amere-diakhatou-1kl.html`). Starting from
`HOME_URL`, this regex-matches every `id-slug` href that is NOT a product
link, treats each as a category entry point, and recurses: every fetched
category page is itself scanned for further `id-slug` links, so nested
subcategories not present on the homepage nav are still reached. A shared
`seen` set (keyed by category id) prevents re-crawling.

Product cards are located via the `data-id-product` attribute PrestaShop
stamps on the `.product-miniature` container -- stable across the several
theme variants seen in this wave (default "laber"/Warehouse theme, and the
"tv"/tvproduct theme used by Diarle). Name/price extraction therefore uses
XPath `string()` aggregation scoped to `[itemprop="name"]` /
`[itemprop="price"]` rather than a fixed tag shape, because some themes wrap
the name in an `<a>` inside the itemprop element and others wrap the
itemprop element inside the `<a>`; a plain `.price` class is tried as a
fallback for themes (Diarle) that drop the `itemprop="price"` microdata.

Some installs (Sakanal, Diarle -- same operator/theme) show a TTC headline
price plus per-payment-method discount rows (`div.remise span.test`, e.g.
"ESPECES: 7 752 FCFA (-5%)"); when present these are emitted as additional
priced variants of the same product (product_id suffixed by payment label)
rather than dropped, matching prior-research guidance to capture all three
price nodes, not just the TTC headline.

Underscored filename -- Scrapy's SpiderLoader skips classes without `name`.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Iterator
from urllib.parse import urljoin

import scrapy

from ..archived import meta_tags, row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)

_ARCHIVE_PRODUCT_ID_RE = re.compile(r"/(\d+)-[a-z0-9\-]+\.html")

CATEGORY_HREF_RE = re.compile(r'href="(https?://[^"\s]+?/(\d+)-[a-z0-9\-]+/?)"')
SKIP_URL_RE = re.compile(
    r"/(cms|content|contact|connexion|login|panier|cart|commande|order|"
    r"mentions-legales|conditions|cgv|livraison|recherche|search|sitemap|"
    r"module|compte|account|adresse|newsletter)[/-]",
    re.IGNORECASE,
)
PRICE_NUM_RE = re.compile(r"\d[\d\s.,]*\d|\d")
REMISE_RE = re.compile(r"([A-Za-zÀ-ÿ ]+):\s*([^()]+)")


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


class PrestashopBaseSpider(scrapy.Spider):
    # Subclasses MUST set: name, allowed_domains, currency, language, HOME_URL.
    name = None
    HOME_URL: str = ""
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_categories: set[str] = set()
        self.total_items = 0
        self.total_category_pages = 0

    async def start(self):
        self.seen_categories.add("")
        yield scrapy.Request(
            self.HOME_URL, callback=self.parse_category, meta={"page": 1}
        )

    def _new_category_requests(self, response):
        for url, cat_id in CATEGORY_HREF_RE.findall(response.text):
            if cat_id in self.seen_categories or SKIP_URL_RE.search(url):
                continue
            self.seen_categories.add(cat_id)
            yield scrapy.Request(
                url, callback=self.parse_category, meta={"page": 1, "cat_url": url}
            )

    def parse_category(self, response):
        yield from self._new_category_requests(response)

        containers = response.css('[itemtype$="/Product"]')
        page = response.meta["page"]
        self.total_category_pages += 1
        n = 0
        for c in containers:
            for item in self._items(c, response):
                n += 1
                yield item
        self.total_items += n
        logger.info(
            f"{self.name}: {response.url} page={page} cards={len(containers)} items={n}"
        )

        cat_url = response.meta.get("cat_url", response.url.split("?")[0])
        if containers and page < self.MAX_PAGES:
            nxt = page + 1
            sep = "&" if "?" in cat_url else "?"
            yield scrapy.Request(
                f"{cat_url}{sep}page={nxt}",
                callback=self.parse_category,
                meta={"page": nxt, "cat_url": cat_url},
            )

    def _items(self, c, response):
        name = c.xpath('string(.//*[@itemprop="name"])').get()
        name = re.sub(r"\s+", " ", name).strip() if name else None
        if not name:
            return
        url = c.xpath(
            '(.//*[@itemprop="name"]/ancestor::a[1]/@href | .//*[@itemprop="name"]//a/@href)[1]'
        ).get()
        product_id = (
            c.attrib.get("data-id-product")
            or c.css("[data-id-product]::attr(data-id-product)").get()
        )
        if not product_id and url:
            m = re.search(r"/(\d+)-[a-z0-9\-]+\.html", url)
            product_id = m.group(1) if m else None
        if not product_id:
            return
        price_text = (
            c.css('[itemprop="price"]::text').get() or c.css(".price::text").get()
        )
        price = normalize_price(price_text) if price_text else None
        category = self._category_label(response)
        full_url = urljoin(response.url, url) if url else response.url

        if price:
            yield {
                "product_id": str(product_id),
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": full_url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        for label, variant_price in self._remise_variants(c):
            yield {
                "product_id": f"{product_id}_{label}",
                "product_name": f"{name[:480]} ({label})",
                "category": category,
                "price": variant_price,
                "currency": self.currency,
                "available": True,
                "url": full_url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

    def _remise_variants(self, c):
        for text in c.css("div.remise span.test::text, div.remise span::text").getall():
            m = REMISE_RE.match(text.strip())
            if not m:
                continue
            label = re.sub(r"[^a-z0-9]+", "_", m.group(1).strip().lower()).strip("_")
            price = normalize_price(m.group(2))
            if label and price:
                yield label, price

    def closed(self, reason):
        # Known silent-failure mode: on themes that never emit schema.org
        # [itemtype$="/Product"] microdata, every category page parses to zero
        # products but the crawl still "succeeds" (200s all the way, no
        # exception, closespider_itemcount never trips because there's
        # nothing to count). Surface that loudly here instead of letting the
        # source ship as a silent zero-row source.
        if self.total_category_pages and self.total_items == 0:
            logger.error(
                f"{self.name}: PrestaShop crawl walked {self.total_category_pages} "
                f"category page(s) across {len(self.seen_categories)} categories and "
                f"emitted ZERO items (reason={reason}). This theme likely doesn't emit "
                '[itemtype$="/Product"] microdata -- see the module docstring. Do not '
                "ship this source without adding a theme-specific selector fallback."
            )

    def _category_label(self, response):
        h1 = response.css("h1::text").get()
        if h1 and h1.strip():
            return h1.strip()
        m = re.search(r"/(\d+)-([a-z0-9\-]+)/?$", response.url.split("?")[0])
        return m.group(2).replace("-", " ") if m else None

    # ------------------------------------------------------------------
    # Crawl backfiller (prices/backfill.py's parse_html hook). Live scrape
    # (_items, above) walks server-rendered category listing pages; archives
    # only ever hold individual product-detail pages, a different surface.
    # Measured on the one PrestaShop tenant with Common Crawl coverage in
    # this wave (galerietata, 8/8 archived PDPs): every page emits standard
    # OpenGraph/`product:price:*` meta, so the shared archived-page meta
    # tier alone is the whole implementation -- no schema.org JSON-LD was
    # present on any sampled page, and no bespoke DOM walk was needed. The
    # only PrestaShop-specific touch is stripping the `<title> - <site
    # name>` suffix PrestaShop's default theme appends to `og:title`, and
    # recovering `product_id` from the `/{id}-{slug}.html` URL convention
    # the same way the live crawl does.
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(cls, html_text: str, url: str) -> Iterator[dict]:
        """Parse one archived PrestaShop product-detail page.

        Pure/stateless: no Scrapy Response, no network, no class state.
        Yields 0 or more rows; yields nothing when the page isn't a product
        page. Does NOT stamp `scraped_at_utc` -- the backfiller stamps the
        snapshot time itself.
        """
        rows = rows_from_jsonld(html_text, url)
        if not rows:
            row = row_from_meta(html_text, url)
            rows = [row] if row else []
        for row in rows:
            row["product_name"] = cls._strip_site_suffix(row["product_name"], html_text)
            if "product_id" not in row:
                m = _ARCHIVE_PRODUCT_ID_RE.search(row.get("url") or url)
                if m:
                    row["product_id"] = m.group(1)
            row.setdefault("currency", cls.currency)
            row.setdefault("language", cls.language)
            yield row

    @staticmethod
    def _strip_site_suffix(name: str, html_text: str) -> str:
        site = meta_tags(html_text).get("og:site_name")
        if site and name.endswith(f" - {site}"):
            return name[: -(len(site) + 3)].strip()
        return name
