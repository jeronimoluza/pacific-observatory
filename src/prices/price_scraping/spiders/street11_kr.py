"""
Spider for 11Street Korea (11st.co.kr) — uses the PUI v2 JSON API that the
SPA itself hydrates from. Playwright is rejected by anti-bot.

The PCBEST page exposes 15 large categories (e.g. 디지털/가전, 의류, 뷰티). Each
category returns ~140 products with prdNo, prdNm, sellPrice, finalDscPrice, and
linkUrl. The page is not paginated — these are curated top-sellers per category.

Uses scrapy-impersonate with safari17_0; Chrome profiles get 403'd by 11st's
anti-bot, same pattern as Rakuten.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

PCBEST_API = "https://apis.11st.co.kr/pui/v2/page"

# 15 large-category tabs discovered by inspecting PCBEST's PC_Tab_ImgText_Expand
# block. Format: (metaCtgrNo, dispCtgrCd, korean_name).
CATEGORIES: list[tuple[str | None, str | None, str]] = [
    (None, None, "전체"),  # all best-sellers (no filter)
    ("167008", "042015", "신선식품"),
    ("167009", "042016", "가공식품"),
    ("157513", "042014", "e쿠폰/상품권"),
    ("153490", "042001", "브랜드패션"),
    ("153506", "042008", "생활용품"),
    ("153496", "042002", "의류"),
    ("153497", "042003", "잡화"),
    ("153499", "042004", "뷰티"),
    ("153503", "042006", "유아동"),
    ("153504", "042007", "가구"),
    ("153507", "042009", "레저/자동차"),
    ("153509", "042010", "디지털/가전"),
    ("153510", "042011", "도서/여행/취미"),
    ("154943", "042012", "해외직구"),
]


class Street11KrSpider(scrapy.Spider):
    name = "street11_kr"
    allowed_domains = ["apis.11st.co.kr", "11st.co.kr", "www.11st.co.kr"]
    currency = "KRW"
    language = "ko"

    IMPERSONATE_PROFILE = "safari17_0"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_product_ids: set[str] = set()

    async def start(self):
        for meta_ctgr, disp_ctgr, name in CATEGORIES:
            qs = ["pageId=PCBEST"]
            if meta_ctgr:
                qs.append(f"metaCtgrNo={meta_ctgr}")
            if disp_ctgr:
                qs.append(f"dispCtgrCd={disp_ctgr}")
            url = f"{PCBEST_API}?{'&'.join(qs)}"
            yield scrapy.Request(
                url,
                callback=self.parse_pui,
                meta={
                    "impersonate": self.IMPERSONATE_PROFILE,
                    "category_name": name,
                },
                errback=self.errback,
                headers={"Accept": "application/json"},
            )

    def parse_pui(self, response):
        category_name = response.meta["category_name"]
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as e:
            logger.error(f"category={category_name} bad JSON: {e}")
            return

        products = list(_iter_products(data))
        scraped_at = datetime.now(timezone.utc).isoformat()
        yielded = 0
        for p in products:
            prd_no = p.get("prdNo")
            prd_nm = p.get("prdNm")
            if not (prd_no and prd_nm):
                continue
            # Prefer the discounted price; fall back to sellPrice.
            price = p.get("finalDscPrice") or p.get("sellPrice")
            if not price:
                continue
            if prd_no in self.scraped_product_ids:
                continue
            self.scraped_product_ids.add(prd_no)
            yield {
                "product_id": prd_no,
                "product_name": prd_nm.strip()[:500],
                "category": category_name,
                "price": price.replace(",", ""),
                "currency": self.currency,
                "url": p.get("linkUrl") or f"https://www.11st.co.kr/products/{prd_no}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            yielded += 1
        logger.info(
            f"category={category_name} candidates={len(products)} yielded={yielded}"
        )

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")


def _iter_products(obj):
    """Walk the PUI JSON tree and yield every dict that looks like a product
    (has prdNo + prdNm + at least one of sellPrice/finalDscPrice)."""
    if isinstance(obj, dict):
        if (
            obj.get("prdNo")
            and obj.get("prdNm")
            and (obj.get("sellPrice") or obj.get("finalDscPrice"))
        ):
            yield obj
        for v in obj.values():
            yield from _iter_products(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_products(v)
