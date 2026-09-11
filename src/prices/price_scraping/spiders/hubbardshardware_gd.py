"""
Hubbard's Hardware (Grenada) -- https://hubbardshardware.gd/.

Magento 2 storefront sharing backend infrastructure with foodfair.gd: its
own /graphql categoryList(id="2") and REST /rest/V1/products both echo
foodfair's grocery catalog (Baby Food & Products, Beverages, ...) rather
than hardware -- confirmed by cross-checking against the real rendered nav,
which lists 88 distinct hardware/houseware/furniture/plumbing category
pages nothing like the GraphQL response. Verdict: GraphQL and REST are
misrouted to the wrong store view for this tenant; only the server-rendered
Luma-theme HTML is trustworthy here, so this uses MagentoSSRBaseSpider
(discovery via the homepage nav) instead.

Bare apex domain (hubbardshardware.gd) silently ignores the `?p=` page
parameter and re-serves page 1 forever -- verified with page1 == page2
byte-identical product list. The `www.` subdomain paginates correctly
(page1/page2/page3 all distinct SKUs). BASE_URL for discovery and every
START_URLS-equivalent link therefore MUST be www.

Page family: listing (category pages), never PDP.
"""

import re

from price_scraping.spiders._magento_base import MagentoSSRBaseSpider

# Matches only the 88 real nav category links (both top-level `level-top`
# items and their `level1` children), verified against the live homepage --
# every href ends in .html and is immediately followed by a title=" attr.
_CATEGORY_URL_RE = re.compile(
    r'href="(https://www\.hubbardshardware\.gd/[a-z0-9][a-z0-9\-/]*\.html)"'
    r'(?:\s+class="level-top")?\s+title="'
)


class HubbardshardwareGdSpider(MagentoSSRBaseSpider):
    name = "hubbardshardware_gd"
    allowed_domains = ["hubbardshardware.gd", "www.hubbardshardware.gd"]
    currency = "XCD"
    language = "en"
    DISCOVERY_URL = "https://www.hubbardshardware.gd/"
    CATEGORY_URL_RE = _CATEGORY_URL_RE
