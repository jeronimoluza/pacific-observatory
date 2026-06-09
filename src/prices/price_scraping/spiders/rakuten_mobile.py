import re
import logging
import scrapy

logger = logging.getLogger(__name__)

_TIER_RE = re.compile(
    r"([^、。\n]*?)([\d,]+)円（税込([\d,]+)円）",
    re.UNICODE,
)

_SLUG_RE = re.compile(r"[^\w]+")


class RakutenMobileSpider(scrapy.Spider):
    name = "rakuten_mobile"
    allowed_domains = ["network.mobile.rakuten.co.jp"]
    start_urls = ["https://network.mobile.rakuten.co.jp/fee/saikyo-plan/"]
    currency = "JPY"
    language = "ja"

    SELECTORS = {
        "price_image": "img[src*='regularPrice']::attr(alt)",
        "plan_name_meta": "meta[property='og:title']::attr(content)",
    }

    def parse(self, response):
        plan_name_base = response.css(self.SELECTORS["plan_name_meta"]).get(
            default="Rakuten最強プラン"
        )
        plan_name_base = plan_name_base.split("（")[0].split("|")[0].strip()

        alts = response.css(self.SELECTORS["price_image"]).getall()

        emitted = set()
        for alt in alts:
            for m in _TIER_RE.finditer(alt):
                tier = m.group(1).strip().rstrip("、。 ")
                price = m.group(2).replace(",", "")
                key = (tier, price)
                if key in emitted or not tier:
                    continue
                emitted.add(key)
                product_name = f"{plan_name_base} — {tier}"
                slug = _SLUG_RE.sub("_", tier).strip("_").lower()
                yield {
                    "product_name": product_name,
                    "price": price,
                    "price_text": m.group(0).strip(),
                    "currency": self.currency,
                    "url": f"{response.url}#{slug}",
                    "language": self.language,
                }

        if not emitted:
            logger.warning(
                "No tier prices extracted from alt attrs on %s", response.url
            )
