"""
Spider for eKupi Croatia — https://ekupi.hr/.

Same SAP Commerce/Hybris platform and template as ekupi.ba (shipped
separately, per-country catalog and currency — Croatia prices in EUR).
Category tree is 2-3 levels deep under /hr/<slug.../c/<CODE> paths; every
page carries the full mega-menu, so the whole tree is discoverable from any
single request. Leaf categories render server-side `product-item` cards
paginated via `?page=N` (0-indexed). Each card embeds a GTM click-tracking
call with the price already in dot-decimal form:
  onClickData('', 'Green Bay roštilj na ugljen Ø 57cm, SRCG22022N',
    'EK000832702', '102.0', 'Green Bay', '',
    '/dom-i-vrt/vrt-i-okucnica/rostilji-peke-i-kotlici/.../p/EK000832702')

Walk: seed with the top-level department links from the homepage nav
(elektronika, računala, kućanski aparati, alati i strojevi, auto i moto
oprema, dom i vrt, igračke, fitness, supermarket, kućni ljubimci); recurse
into any nested /c/<CODE> link found on a page (BFS, deduped by CODE,
capped); on any page carrying product-item cards, paginate ?page=N until a
page yields no product ids beyond what's already seen for that category, or
MAX_PAGES.

Re-verified live 2026-08-17: /hr/dom-i-vrt/vrt-i-okucnica/rostilji-peke-i-
kotlici/c/10307 -> 200, 25 product cards; real product 'Green Bay roštilj
na ugljen Ø 57cm, SRCG22022N' EUR 102,00 (onClickData price field '102.0'
matches). General department-store catalog (electronics, appliances, tools,
auto, home&garden, toys, fitness, supermarket, pets) -> channel: dept-store.
"""

import html
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://ekupi.hr"
_LANG = "hr"
_TOP_CATEGORIES = [
    "elektronika/c/10002",
    "racunala/c/10001",
    "kucanski-aparati/c/10003",
    "alati-i-strojevi/c/10037",
    "auto-i-moto-oprema/c/10005",
    "dom-i-vrt/c/10006",
    "igracke-i-djecja-oprema/c/10008",
    "fitness/c/10031",
    "supermarket/c/10011",
    "kucni-ljubimci/c/13453",
]

_CAT_HREF_RE = re.compile(r'href="(/hr/[a-z0-9\-/]+/c/([A-Z0-9]+))"')
_PRODUCT_RE = re.compile(
    r"onClickData\('', '(.*?)', '([A-Z0-9]+)', '([\d.]+)', '(.*?)', '', '(/[^']*)'\)"
)
MAX_PAGES = 20
MAX_CATEGORY_CODES = 500


class EkupiHrSpider(scrapy.Spider):
    name = "ekupi_hr"
    allowed_domains = ["ekupi.hr"]
    currency = "EUR"
    language = _LANG

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_codes: set[str] = set()

    async def start(self):
        for slug in _TOP_CATEGORIES:
            code = slug.rsplit("/", 1)[-1]
            self.seen_codes.add(code)
            path = f"/{_LANG}/{slug}"
            yield scrapy.Request(
                urljoin(_BASE, path),
                callback=self.parse_category,
                meta={"page": 0, "seen_products": set(), "cat_path": path},
            )

    @staticmethod
    def _category(cat_path: str) -> str:
        parts = cat_path.strip("/").split("/")
        return parts[-3] if len(parts) >= 3 else parts[-1]

    def parse_category(self, response):
        for href, code in _CAT_HREF_RE.findall(response.text):
            if code in self.seen_codes or len(self.seen_codes) >= MAX_CATEGORY_CODES:
                continue
            self.seen_codes.add(code)
            path = href.split("?")[0]
            yield scrapy.Request(
                urljoin(_BASE, path),
                callback=self.parse_category,
                meta={"page": 0, "seen_products": set(), "cat_path": path},
            )

        page = response.meta["page"]
        seen_products: set = response.meta["seen_products"]
        cat_path = response.meta["cat_path"]
        category = self._category(cat_path)

        matches = _PRODUCT_RE.findall(response.text)
        new = [m for m in matches if m[1] not in seen_products]
        scraped_at = datetime.now(timezone.utc).isoformat()
        for name, pid, price, _brand, url_path in new:
            yield {
                "product_id": pid,
                "product_name": html.unescape(name).strip()[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": urljoin(_BASE, url_path),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(
            f"{self.name}: {cat_path} page={page} cards={len(matches)} new={len(new)}"
        )

        if new and page < MAX_PAGES:
            updated_seen = seen_products | {m[1] for m in matches}
            sep = "&" if "?" in cat_path else "?"
            yield scrapy.Request(
                f"{urljoin(_BASE, cat_path)}{sep}page={page + 1}",
                callback=self.parse_category,
                meta={
                    "page": page + 1,
                    "seen_products": updated_seen,
                    "cat_path": cat_path,
                },
            )
