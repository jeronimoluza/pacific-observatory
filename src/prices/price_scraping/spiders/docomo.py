import re
import logging
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"([\d,]+)円")
_SLUG_RE = re.compile(r"[^\w]+")


class DocomoSpider(CrawlSpider):
    name = "docomo"
    allowed_domains = ["www.docomo.ne.jp"]
    start_urls = ["https://www.docomo.ne.jp/charge/"]
    currency = "JPY"
    language = "ja"

    SELECTORS = {
        "plan_block": "li.list-common__item--normal",
        "plan_name": "dl.mod-txt-common dt::text",
        "price_text": "dl.mod-txt-common dd::text",
    }

    rules = (
        Rule(
            LinkExtractor(
                allow=r"/charge/(?!index)",
                deny=r"(/simulation|/campaign|/discount|/news|/support|icid=)",
                restrict_css="section#sec_plan, section.sec-list-option",
            ),
            callback="parse_plan_page",
            follow=False,
        ),
    )

    def parse_start_url(self, response, **kwargs):
        yield from self._extract_items(response)

    def parse_plan_page(self, response):
        yield from self._extract_items(response)

    def _extract_items(self, response):
        blocks = response.css(self.SELECTORS["plan_block"])
        for block in blocks:
            name = block.css(self.SELECTORS["plan_name"]).get()
            price_raw = block.css(self.SELECTORS["price_text"]).get()
            if not name or not price_raw:
                continue
            name = name.strip()
            m = _PRICE_RE.search(price_raw)
            if not m:
                continue
            price = m.group(1).replace(",", "")
            slug = _SLUG_RE.sub("_", name).strip("_").lower()
            yield {
                "product_name": name,
                "price": price,
                "price_text": price_raw.strip(),
                "currency": self.currency,
                "url": f"{response.url}#{slug}",
                "language": self.language,
            }
