"""Global Product Prices Cameroon food indicators."""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)


class CameroonGlobalProductPricesSpider(scrapy.Spider):
    name = "cameroon_globalproductprices"
    allowed_domains = ["globalproductprices.com", "www.globalproductprices.com"]
    start_urls = ["https://www.globalproductprices.com/Cameroon/"]
    currency = "XAF"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 1,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def parse(self, response):
        if response.status == 429:
            logger.warning("cameroon_globalproductprices: HTTP 429; stopping")
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        # The page's food section is delimited by the food heading and the
        # following section heading. Each indicator is a sibling row/block.
        food_heading = response.css(".indicatorsCategoryTitle").xpath(
            ".//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'basic food items')]"
        )
        food_heading = food_heading[0] if food_heading else None
        if not food_heading:
            logger.warning("cameroon_globalproductprices: food section not found")
            return
        section = food_heading.xpath("ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' indicatorsCategory ')][1]")
        section = section[0] if section else None
        if not section:
            return
        rows = section.xpath(".//*[contains(@class, 'indicatorsName')]") if section else []
        for name_node in rows:
            link = name_node.xpath(".//a[1]")
            name = " ".join(link.xpath(".//text()").getall()).strip()
            if not name:
                continue
            # Keep only food indicators; the site's food block uses this
            # naming convention and avoids non-food household rows.
            row = name_node.xpath("ancestor::*[.//*[contains(@class, 'indicatorsLastValue')]][1]")
            values = [" ".join(x.xpath(".//text()").getall()).strip() for x in row.xpath(".//*[contains(@class, 'indicatorsLastValue')]")]
            date = " ".join(row.xpath(".//*[contains(@class, 'indicatorsLastValueDate')]//text()").getall()).strip()
            measure = " ".join(row.xpath(".//*[contains(@class, 'indicatorsMeasure')]//text()").getall()).strip()
            if not values or not re.search(r"XAF", values[0], re.I):
                continue
            local = re.search(r"([0-9][0-9 .,]*)\s*XAF", values[0], re.I)
            usd = re.search(r"([0-9][0-9 .,]*)\s*USD", " ".join(values), re.I)
            if not local:
                continue
            yield {
                "product_name": name,
                "price": float(local.group(1).replace(" ", "").replace(",", "")),
                "currency": self.currency,
                "price_usd": float(usd.group(1).replace(" ", "").replace(",", "")) if usd else None,
                "unit": link.xpath("@title").get() or name,
                "measure": measure or None,
                "date": date or None,
                "url": response.urljoin(link.xpath("@href").get() or response.url),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
