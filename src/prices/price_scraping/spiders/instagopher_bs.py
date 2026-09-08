"""
Instagopher (The Bahamas) -- https://instagopher.com/.

"Instant Affordable Online Grocery Store In Bahamas" -- a Nassau /
Paradise Island online grocery delivering to homes, hotels, timeshares,
condos, vacation rentals and marinas.

Magento 2 (Luma theme), server-rendered. /graphql is 404 and no REST
surface is exposed, but category listings ship `product-item-link` name
anchors and `data-price-amount` price attributes directly in the markup --
exactly the shape `MagentoSSRBaseSpider` handles. Enumerability verified
live 2026-09-05: /beverages/wine/red-wine and .../red-wine?p=2 each return
24 cards with 24 prices and fully disjoint product sets.

Category discovery is done from the homepage rather than a hardcoded list:
the storefront has exactly two roots (`beverages`, `groceries`) and 56
sub-paths under them, all linked from the homepage nav. The regex below
matches roots plus any depth of sub-path, and deliberately does NOT match
the single-segment product URLs the homepage also links (e.g.
/1-dozen-eggs, /anchor-salted-butter) -- those are PDPs, not listings.

Currency: prices render as "$" and the operator is Nassau-based. BSD is
pegged 1:1 to USD; recorded as BSD here to match this country's
`solomonsfreshmarkets_bs` / `kellysbahamas_bs` convention, since unlike
`foodstore2go_bs` (Shopify, which declares USD machine-readably) this
storefront states no ISO currency code anywhere.
"""

import re

from price_scraping.spiders._magento_base import MagentoSSRBaseSpider


class InstagopherBsSpider(MagentoSSRBaseSpider):
    name = "instagopher_bs"
    allowed_domains = ["instagopher.com"]
    currency = "BSD"
    language = "en"

    DISCOVERY_URL = "https://instagopher.com/"
    CATEGORY_URL_RE = re.compile(
        r'href="(https://instagopher\.com/(?:beverages|groceries)(?:/[a-z0-9\-]+)*)"'
    )
    PAGE_PARAM = "p"
