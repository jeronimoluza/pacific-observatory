import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

API_URL = "https://api.2degrees.nz/ecommerce/v1/plans?channel=web"

PAY_MONTHLY_IDS = {
    "Mobile2_2D_Carryover_C02500",
    "Mobile2_2D_Carryover_C02501",
    "Mobile2_2D_Carryover_C02502",
    "1-59TBF4",
    "1-13KHMK",
    "1-56QTBG",
    "1-54P4IX",
}


class TwoDegreesNzSpider(scrapy.Spider):
    name = "two_degrees_nz"
    allowed_domains = ["api.2degrees.nz", "www.2degrees.nz"]
    currency = "NZD"
    language = "en"

    SELECTORS = {
        "plan_name": "itemDisplayName",
        "price_incl_gst": "itemRRPAmount",
        "product_id": "itemProductId",
        "plan_data": "itemPlanData",
        "plan_type": "itemPlanType",
        "segment": "segment",
    }

    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "RETRY_TIMES": 3,
        "DOWNLOAD_TIMEOUT": 30,
    }

    def start_requests(self):
        yield scrapy.Request(
            API_URL,
            callback=self.parse_plans,
            headers={
                "Accept": "application/json",
                "Referer": "https://www.2degrees.nz/mobile-plans/pay-monthly",
                "Origin": "https://www.2degrees.nz",
            },
        )

    def parse_plans(self, response):
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from {response.url}")
            return

        plans = data.get("productDetails", [])
        scraped_at = datetime.now(timezone.utc).isoformat()
        page_url = "https://www.2degrees.nz/mobile-plans/pay-monthly"

        for plan in plans:
            product_id = plan.get(self.SELECTORS["product_id"]) or ""
            if product_id not in PAY_MONTHLY_IDS:
                continue

            price_raw = plan.get(self.SELECTORS["price_incl_gst"])
            if not price_raw or str(price_raw) == "0":
                continue

            yield {
                "product_id": product_id,
                "product_name": plan.get(self.SELECTORS["plan_name"], "").strip()[:500],
                "category": "mobile-plans/pay-monthly",
                "price": str(price_raw),
                "currency": self.currency,
                "url": f"{page_url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
