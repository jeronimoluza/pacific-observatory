"""
Spider for zap.co.il — Israel price-comparison shopping engine (NOT a
single retailer).

The homepage carries no prices (client-side search only). Category pages
(models.aspx?sog=<code>) ARE server-rendered but only expose a thin
sponsored-bid panel (a handful of real ₪ prices per page, `?pg=` doesn't
paginate it) — the full model grid itself is client-rendered. What DOES
carry rich pricing is each model's own comparison page
(model.aspx?modelid=<id>): confirmed live 2026-08-17 on modelid=1253558
(Apple iPhone 17 256GB) — 56 `class="product-name"` / `class="price"`
span pairs in strict alternating order, one per participating store's
offer, real ILS prices (e.g. 2,826 / 3,490 / ...).

So this spider two-hops: each category page is scraped for every
`modelid=(\\d+)` reference (from both the legacy `data-model-id` bid
template and the newer `card-v2` href pattern), capped at
MAX_MODELS_PER_CATEGORY distinct model ids, then each model's comparison
page is fetched and every store-offer row on it is emitted. Treated as
analytical_role: aggregate_proxy / channel: other, same caveat as
torob_ir — each row is one store's own listed price (not a
comparison-engine minimum like torob), but the source itself is a
shopping-comparison site, not a retailer.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "e-cellphone",
    "e-cellwatch",
    "e-tv",
    "e-camera",
    "e-headphone",
    "e-airconditioner",
    "e-coffeemachine",
    "e-dishwasher",
    "e-drayer",
    "e-fan",
    "e-fridge",
    "e-hobs",
    "e-oven",
    "e-tvgame",
    "e-vaccumcleaner",
    "e-washingmachine",
    "c-pcdesktop",
    "c-pclaptop",
    "c-monitor",
    "c-printer",
    "c-tabletpc",
    "c-gamingchair",
    "b-perfume",
    "b-shampoo",
    "b-aftershave",
    "b-tooth",
    "g-watch",
    "g-jewlery",
    "h-drill",
    "h-grill",
    "h-taps",
    "h-bags",
    "k-furniture",
    "k-lego",
    "k-safetyseat",
    "s-treadmill",
    "s-weight",
    "s-tent",
    "t-speakers",
    "t-amplifier",
    "p-shoe",
]
MAX_MODELS_PER_CATEGORY = 25

_MODEL_ID_RE = re.compile(r"modelid=(\d{6,})")
_ROW_RE = re.compile(
    r'class="product-name">([^<]+)</span>|class="price">([\d,]+)</span>'
)


class ZapIlSpider(scrapy.Spider):
    name = "zap_il"
    allowed_domains = ["zap.co.il"]
    currency = "ILS"
    language = "he"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for code in _CATEGORIES:
            yield scrapy.Request(
                f"https://www.zap.co.il/models.aspx?sog={code}",
                callback=self.parse_category,
                meta={"code": code},
            )

    def parse_category(self, response):
        code = response.meta["code"]
        model_ids = list(dict.fromkeys(_MODEL_ID_RE.findall(response.text)))
        model_ids = model_ids[:MAX_MODELS_PER_CATEGORY]
        logger.info("zap_il: category=%s model_ids=%d", code, len(model_ids))
        for model_id in model_ids:
            yield scrapy.Request(
                f"https://www.zap.co.il/model.aspx?modelid={model_id}",
                callback=self.parse_model,
                meta={"code": code, "model_id": model_id},
            )

    def parse_model(self, response):
        code = response.meta["code"]
        model_id = response.meta["model_id"]
        scraped_at = datetime.now(timezone.utc).isoformat()

        rows = []
        pending_name = None
        for m in _ROW_RE.finditer(response.text):
            if m.group(1) is not None:
                pending_name = m.group(1).strip()
            elif m.group(2) is not None and pending_name:
                rows.append((pending_name, m.group(2)))
                pending_name = None

        n = 0
        for i, (name, price) in enumerate(rows):
            price = price.replace(",", "")
            if not name or not price:
                continue
            n += 1
            yield {
                "product_id": f"{model_id}_{i}",
                "product_name": name[:500],
                "category": code,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: model_id={model_id} offers={n}")
