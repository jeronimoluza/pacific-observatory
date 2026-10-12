"""
Spider for Aruba's Online Giftshop (Aruba) - arubasonlinegiftshop.com

JouwWeb/Jimdo webshop. sitemap.xml lists every /product/<id>/<slug> PDP; the PDP
carries itemprop price/priceCurrency meta tags (AWG) and an itemprop=name h1.
Page family: PDP.
"""

import logging
from datetime import datetime, timezone

from scrapy.spiders import SitemapSpider

logger = logging.getLogger(__name__)


class ArubasonlinegiftshopAwSpider(SitemapSpider):
    name = "arubasonlinegiftshop_aw"
    allowed_domains = ["www.arubasonlinegiftshop.com", "arubasonlinegiftshop.com"]
    sitemap_urls = ["https://www.arubasonlinegiftshop.com/sitemap.xml"]
    sitemap_rules = [(r"/product/\d+/", "parse_product")]
    currency = "AWG"

    custom_settings = {"DOWNLOAD_DELAY": 1, "CONCURRENT_REQUESTS": 1}

    def parse_product(self, response):
        name = " ".join(
            "".join(response.css("h1.product-page__heading *::text, h1[itemprop='name'] *::text").getall()).split()
        ) or response.css("meta[property='og:title']::attr(content)").get()
        price = response.css("meta[itemprop='price']::attr(content)").get()
        if not (name and price):
            logger.warning("Could not extract product data from %s", response.url)
            return
        product_id = response.url.split("/product/", 1)[-1].split("/", 1)[0]
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "price": price,
            "currency": response.css("meta[itemprop='priceCurrency']::attr(content)").get() or self.currency,
            "category": None,
            "url": response.url,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
