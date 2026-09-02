"""
Unitel T+ (Cabo Verde mobile/fixed operator) — https://www.uniteltmais.cv/.

The public tariff pages (/private/mobile/mobile-plans/play,
/private/mobile/internet) are Next.js pages, but -- unlike
/private/mobile/mobile-plans/classic and /home, which only embed an HTML
table inside a CMS rich-text string -- these two server-render their plan
data straight into the page's __NEXT_DATA__ JSON, so a plain HTML GET
(Tier 1A, no extra API call, no Playwright) is enough:

  pageProps.pageData.plans.plans[]            -> {id, translations.name, price}
  pageProps.pageData.first_data_plans.plans[] -> {type, price, first_activation}
  pageProps.pageData.second_data_plans.plans[]-> same shape, second SIM-data line

Verified live 2026-08-31: "play" page has 3 prepaid voice+data bundles
(High Score / I / II, 500/700/1000 CVE); "internet" page has 3 standalone
4G data plans (2500/3500/4299 CVE) plus two named data-bundle ladders
("NET PARA TELEMOVEL" 5 tiers, "NET VIVA+ PARA PEN/PC" 6 tiers), all
priced in escudos (CVE). Other tariff pages under /private/mobile and
/private/home either carry no `plans`/`*_data_plans` key or bury pricing
inside a rich-text HTML table (classic/home) and are intentionally not
scraped here rather than guessed at.

Every plan on a page shares that page's URL; DuplicationPipeline dedups on
item['url'], so each row's url is the page URL plus a '#<plan-id>' or
'#<ladder>-<n>' fragment.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.uniteltmais.cv"
PAGES = [
    "/private/mobile/mobile-plans/play",
    "/private/mobile/internet",
]

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


class UnitelTplusCvSpider(scrapy.Spider):
    name = "unitel_tplus_cv"
    allowed_domains = ["uniteltmais.cv"]
    currency = "CVE"
    language = "pt"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for path in PAGES:
            yield scrapy.Request(
                f"{BASE_URL}{path}",
                callback=self.parse_page,
                errback=self.errback,
                meta={"path": path},
            )

    def parse_page(self, response):
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning(f"{self.name}: no __NEXT_DATA__ on {response.url}")
            return
        try:
            next_data = json.loads(m.group(1))
        except ValueError:
            logger.warning(f"{self.name}: bad __NEXT_DATA__ JSON on {response.url}")
            return

        page_data = (
            next_data.get("props", {}).get("pageProps", {}).get("pageData") or {}
        )
        now = datetime.now(timezone.utc).isoformat()
        path = response.meta["path"]
        emitted = 0

        plans = (page_data.get("plans") or {}).get("plans") or []
        for plan in plans:
            price = plan.get("price")
            name = (plan.get("translations") or {}).get("name")
            plan_id = plan.get("id")
            if price is None or not name:
                continue
            emitted += 1
            yield {
                "product_id": f"{path.strip('/')}-{plan_id}",
                "product_name": name[:500],
                "category": "mobile_plan",
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": f"{response.url}#plan-{plan_id}",
                "language": self.language,
                "scraped_at_utc": now,
            }

        for ladder_key in ("first_data_plans", "second_data_plans"):
            ladder = page_data.get(ladder_key) or {}
            headline = (ladder.get("translations") or {}).get("headline") or ladder_key
            for i, tier in enumerate(ladder.get("plans") or []):
                price = tier.get("price")
                if price is None:
                    continue
                name = (
                    f"{headline} — {tier.get('type', '')} "
                    f"{tier.get('first_activation', '')}".strip()
                )
                emitted += 1
                yield {
                    "product_id": f"{path.strip('/')}-{ladder_key}-{i}",
                    "product_name": name[:500],
                    "category": "mobile_data_plan",
                    "price": str(price),
                    "currency": self.currency,
                    "available": True,
                    "url": f"{response.url}#{ladder_key}-{i}",
                    "language": self.language,
                    "scraped_at_utc": now,
                }

        logger.info(f"{self.name}: {response.url} emitted={emitted}")

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
