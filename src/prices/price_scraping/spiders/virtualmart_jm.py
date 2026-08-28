"""
Spider for Virtual Mart Jamaica — https://www.virtualmartja.com/.

Magento SSR HTML with data-price-amount markup. Mixed grocery +
hardware/business-supplies store (CSV note), so per the "whole-catalog
walker" rule this crawls the site's own shop-by-category.html directory
(42 top-level departments spanning groceries through automotive/hardware)
rather than filtering to a food subset. Each department page paginates
with the standard Magento ?p=N param (verified: page 2 returns different
products than page 1). The redirect chain off the bare domain sets a store
+ session cookie; Scrapy's default cookie jar follows it transparently, so
DISCOVERY_URL can point straight at shop-by-category.html.
"""

import re

from price_scraping.spiders._magento_base import MagentoSSRBaseSpider

_CATEGORY_URL_RE = re.compile(
    r'href="(https://virtualmartja\.com/default/shop-by-category\.html\?cat=\d+)"'
)


class VirtualmartJmSpider(MagentoSSRBaseSpider):
    name = "virtualmart_jm"
    allowed_domains = ["virtualmartja.com"]
    currency = "JMD"
    language = "en"

    DISCOVERY_URL = "https://www.virtualmartja.com/shop-by-category.html"
    CATEGORY_URL_RE = _CATEGORY_URL_RE
    PAGE_PARAM = "p"
