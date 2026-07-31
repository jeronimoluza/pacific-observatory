"""
Spider for Gmarket Korea (gmarket.co.kr) — eBay Korea / Shinsegae (Emart)
open marketplace. The best-seller pages are Next.js server-rendered: the
`__NEXT_DATA__` script tag carries the full priced product list, so no
client-side XHR or Playwright is needed.

Cloudflare fronts the site but curl_cffi's chrome TLS impersonation passes
the __cf_bm bot-management check on a datacenter IP. Requests set
meta['impersonate']='chrome' and disable the random-browser middleware so the
profile stays fixed.

Scoped to the three grocery large-category groups (groupCode): 신선식품
(fresh food), 가공식품 (processed food), 생필품/육아 (daily necessities).
Each ?groupCode=... page returns ~200 ranked best-sellers with goodsCode,
goodsName and sellPrice (KRW integer).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BEST_URL = "https://www.gmarket.co.kr/n/best?groupCode={code}"

# (groupCode, korean_label) for grocery large-category tabs on /n/best.
GROUPS: list[tuple[str, str]] = [
    ("100000006", "신선식품"),  # fresh food
    ("100000005", "가공식품"),  # processed food
    ("100000007", "생필품/육아"),  # daily necessities / baby
]

_NEXT_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


class GmarketSpider(scrapy.Spider):
    name = "gmarket"
    allowed_domains = ["gmarket.co.kr", "www.gmarket.co.kr"]
    currency = "KRW"
    language = "ko"

    IMPERSONATE_PROFILE = "chrome"
    # Cloudflare cross-checks the User-Agent against the TLS fingerprint; a
    # Scrapy-default UA with a chrome TLS profile is 403'd, so pin a matching
    # Chrome UA.
    CHROME_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "USER_AGENT": CHROME_UA,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "ROBOTSTXT_OBEY": False,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_product_ids: set[str] = set()

    async def start(self):
        for code, label in GROUPS:
            yield scrapy.Request(
                BEST_URL.format(code=code),
                callback=self.parse_best,
                meta={"impersonate": self.IMPERSONATE_PROFILE, "category": label},
                headers={"User-Agent": self.CHROME_UA},
                errback=self.errback,
            )

    def parse_best(self, response):
        category = response.meta["category"]
        m = _NEXT_RE.search(response.text)
        if not m:
            logger.error(f"gmarket: no __NEXT_DATA__ for {response.url}")
            return
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError as e:
            logger.error(f"gmarket: bad __NEXT_DATA__ json ({category}): {e}")
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        yielded = 0
        products = list(_iter_products(data))
        for p in products:
            code = str(p.get("goodsCode"))
            name = (p.get("goodsName") or "").strip()
            price = _pick_price(p)
            if not code or not name or price is None:
                continue
            if code in self.scraped_product_ids:
                continue
            self.scraped_product_ids.add(code)
            yield {
                "product_id": code,
                "product_name": name[:500],
                "price": str(price),
                "currency": self.currency,
                "category": category,
                "url": f"https://item.gmarket.co.kr/Item?goodscode={code}",
                "language": self.language,
                "scraped_at": scraped_at,
            }
            yielded += 1
        logger.info(
            f"gmarket: category={category} candidates={len(products)} yielded={yielded}"
        )

    def errback(self, failure):
        logger.error(
            f"gmarket request failed: {failure.request.url} — {failure.value!r}"
        )


def _pick_price(p: dict):
    val = p.get("sellPrice")
    if val is None:
        val = p.get("itemPrice")
    if val is None:
        info = p.get("couponAppliedPriceInfo")
        if isinstance(info, dict):
            val = info.get("couponAppliedPrice")
    if val is None:
        return None
    if isinstance(val, str):
        val = val.replace(",", "").strip()
    return val or None


def _iter_products(obj):
    """Walk __NEXT_DATA__ and yield dicts that look like a priced product
    (goodsCode + at least one price field)."""
    if isinstance(obj, dict):
        if obj.get("goodsCode") and (
            obj.get("sellPrice") is not None
            or obj.get("itemPrice") is not None
            or isinstance(obj.get("couponAppliedPriceInfo"), dict)
        ):
            yield obj
        for v in obj.values():
            yield from _iter_products(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_products(v)
