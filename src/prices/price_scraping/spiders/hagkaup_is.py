"""
Hagkaup — https://www.hagkaup.is/ (Iceland national supermarket chain, Hagar hf).

Magento 2 storefront. The site's own /graphql (405) is closed, but the
shared backend at mcprod.mobileapp.is/graphql (Hagar-group media/API host,
same "mcprod.<domain>" Magento-Cloud naming convention seen on other
mcprod.* sources in this repo) is wide open with no auth. Verified live
2026-09-06 with curl_cffi impersonate=chrome124: 200, standard categoryList
-> products(filter:{category_id}) shape. Uses the shared
`_magento_base.MagentoGraphQLBaseSpider`.

PDP URL override: the base class's default `BASE_URL + "/" + url_key`
construction is wrong for this storefront -- real PDP URLs are
`/vara/<url_key>` (confirmed live: a category page's own product anchors
are `/vara/muna-acidophilus-120-stk-1221133`, and `url_key` from GraphQL
already includes the trailing numeric id, e.g.
"follow-the-call-of-the-disco-lengja-1209665"). Same "/vara/" PDP prefix
as kronan_is, Iceland's other Magento-family competitor already onboarded
in this repo. `_item()` is overridden here rather than touching the
shared base, since other Magento sources rely on the base's default.
"""

import html
from datetime import datetime, timezone

from price_scraping.spiders._magento_base import MagentoGraphQLBaseSpider


class HagkaupIsSpider(MagentoGraphQLBaseSpider):
    name = "hagkaup_is"
    allowed_domains = ["hagkaup.is", "mobileapp.is"]
    currency = "ISK"
    language = "is"

    GRAPHQL_URL = "https://mcprod.mobileapp.is/graphql"
    BASE_URL = "https://www.hagkaup.is"
    ROOT_CATEGORY_ID = "2"

    def _item(self, p: dict):
        name = (p.get("name") or "").strip()
        price_block = ((p.get("price_range") or {}).get("minimum_price") or {}).get(
            "final_price"
        ) or {}
        value = price_block.get("value")
        if not name or value is None:
            return None
        return {
            "product_id": str(p.get("sku") or ""),
            "product_name": html.unescape(name)[:500],
            "category": None,
            "price": str(value),
            "currency": price_block.get("currency") or self.currency,
            "available": True,
            "url": f"{self.BASE_URL}/vara/{p.get('url_key') or ''}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
