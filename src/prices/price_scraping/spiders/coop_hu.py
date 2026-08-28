"""
Spider for Coop Online (Hungary) -- https://vasarlas.coop.hu/.

The shard CSV listed this as OpenCart (its URLs use `route=product/list` /
`route=product/quickview&product_id=N`, an OpenCart-style convention), but
re-verification shows the actual storefront is served by Shoprenter
(`cdn.shoprenter.hu` assets, `Currency={"currency":"HUF",...}` JS globals) --
a different Hungarian SaaS platform that happens to keep OpenCart-compatible
route params, likely a legacy migration artifact. It is scaffolded here as a
one-off `scrapy_html` source rather than on the `_opencart_base` shared
class, since none of that base's selectors match this theme.

Category discovery: the homepage nav marks every category (including nested
children) with `<li id="cat_<id>" class="... category-list ...">`, which
cleanly distinguishes categories from products -- product detail URLs share
the same trailing `-<id>` shape as category URLs on this platform, so the
nav-list marker (rather than URL shape) is what this relies on. The whole
tree is exposed in one homepage fetch, so no recursive category-page
crawling is needed.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

CATEGORY_LI_RE = re.compile(
    r'<li id="cat_\d+" class="[^"]*category-list[^"]*"[^>]*>\s*<a href="([^"]+)"'
)
PRICE_NUM_RE = re.compile(r"\d[\d\s.,]*\d|\d")


def normalize_price(raw: str) -> str | None:
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


class CoopHuSpider(scrapy.Spider):
    name = "coop_hu"
    allowed_domains = ["coop.hu"]
    currency = "HUF"
    language = "hu"
    HOME_URL = "https://vasarlas.coop.hu/"
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
        yield scrapy.Request(self.HOME_URL, callback=self.parse_home)

    def parse_home(self, response):
        seen = set()
        for href in CATEGORY_LI_RE.findall(response.text):
            url = urljoin(response.url, href)
            if url in seen:
                continue
            seen.add(url)
            yield scrapy.Request(
                url, callback=self.parse_category, meta={"page": 1, "cat_url": url}
            )

    def parse_category(self, response):
        cards = response.css("div.product-card")
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

    def _item(self, card, response):
        name = card.css("h2.product-card-title a::text").get()
        url = card.css("h2.product-card-title a::attr(href)").get()
        if not name or not name.strip():
            return None
        price_text = card.css(
            ".product-price-special::text, span.product-price::text"
        ).get()
        price = normalize_price(price_text) if price_text else None
        if not price:
            return None
        full_url = urljoin(response.url, url) if url else response.url
        m = re.search(r"-(\d+)$", full_url.rstrip("/"))
        product_id = m.group(1) if m else full_url
        return {
            "product_id": product_id,
            "product_name": name.strip()[:500],
            "category": self._category_label(response),
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": full_url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def _category_label(self, response):
        h1 = response.css("h1::text").get()
        return h1.strip() if h1 else None
