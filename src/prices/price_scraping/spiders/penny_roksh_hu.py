"""
Spider for Penny Market Hungary via the ROKSH personal-shopper platform --
https://www.roksh.com/ (briefed candidate: "roksh_hu").

The briefed endpoint (`roksh-backend.roksh.com/api/translations/get/0/hu`)
is exactly the "widget, not enumeration route" case: a UI string
dictionary, not catalog data -- but it does prove roksh-backend.roksh.com
answers anonymously, which pointed at the platform being worth a full
network trace.

roksh.com is a MULTI-TENANT personal-shopper marketplace, not a single
retailer -- `GET https://shopservice.roksh.com/api/Provider/GetAllProviders`
(wide open, no auth) lists 15 tenants: ALDI (already onboarded in this
tree as `aldi_roksh_hu.py`, targeting the dedicated `shop.aldi.hu`
storefront), Toman Diet, Penny (`PENNY-HU`), Bijó, SZEGA Foods, Alphazoo,
Beerselection, Alphazoocampona, Party Point, Szimpatika Alkotás
Gyógyszertár (a pharmacy), METRO (`METRO_HU`), REGIO JÁTÉK (a toy store),
chocoMe, Dolce Burata, Mcsemege. This spider targets ONLY `PENNY-HU` --
Penny Market, a real, large Hungarian discount-supermarket chain not
otherwise present in this tree, and NOT Aldi's catalog re-served (see
below for how that was ruled out). METRO_HU, SZIMPATIKA5-HU and
CHOCOME-HU were spot-checked live on the same endpoint used below and all
returned HTTP 500 -- likely account/session prerequisites this pass did
not investigate (Penny worked with zero session setup) -- so this spider
does NOT attempt the other 13 tenants; each would need its own probe
pass, out of scope here. Named `penny_roksh_hu` (tenant-first, platform-
second) to match the `aldi_roksh_hu` naming convention already in this
tree, rather than a bare `roksh_hu` that would wrongly imply full-
platform coverage.

Platform mechanics (Angular SPA; backend at `shopservice.roksh.com`, no
auth needed for any call below, confirmed live 2026-09-10):

  - `GET /category/GetFullCategoryList?providerCode=PENNY-HU&isOwnWebshop=false`
    -> the platform's SHARED category taxonomy (confirmed near-identical
    in size/shape to the same call with providerCode=ALDI -- this is not
    a per-tenant tree, just the global one), 383 leaf ProgIDs.
  - `GET /productlist/additionalCategoryProductList?...&providerCode=PENNY-HU`
    (the endpoint aldi_roksh_hu.py uses with `isOwnWebshop=true`) does
    NOT correctly scope to Penny when isOwnWebshop is false/absent --
    confirmed live: it returned a product whose `productProvider[0]
    .providerID` was 66 (METRO_HU) regardless of the providerCode param,
    and stayed that way even with isOwnWebshop=true added (only Aldi's
    dedicated shop.aldi.hu domain gets real single-tenant scoping from
    that path). Abandoned that endpoint for this tenant.
  - `GET /productlist/CategoryProductList?providerCode=PENNY-HU&progId=<leaf>
    &page=1&numberOfItems=<n>` IS correctly scoped -- confirmed live:
    progId=friss-tej (fresh milk) returns 7 products, every one's
    `productProvider[0].providerID == 19` (Penny's own provider id) and
    `productDetails.supplierAddress` = "Penny Market Kft., 2351
    Alsónémedi, Penny utca 2., Magyarország" -- Penny's real registered
    address, not a generic/shared value, confirming this is genuinely
    Penny's own catalog and not Aldi's or METRO's re-served under a
    different label. This is the endpoint this spider uses.

Enumerability: leaf catalogs are small (Penny's `friss-tej`=7,
`kemeny-sajt`=4, `grill-sajtok`=0 -- not every leaf is stocked), so
in-leaf pagination is not needed (same shape as aldi_roksh_hu); distinct
leaves return entirely distinct, non-overlapping product-id sets
(spot-checked friss-tej vs kemeny-sajt: 0 shared ids) which is this
platform's enumerability proof. A 40-leaf sample (of 383) returned 33
non-empty leaves and 193 products -- extrapolated whole-catalog size on
the order of ~1,800 products. `numberOfItems=500` is set well above any
observed leaf size so no leaf's true count is truncated.

Price/name/category live on the ProductList row itself (real HUF prices,
e.g. "Sissy ESL félzsíros tej 2,8% 1 l" HUF 295.00), not nested under
`productProvider[0]` (that array duplicates name/price per offering
provider but the row-level fields are Penny's own, matching precisely
when there's exactly one provider in the array, as is always true here
since providerCode already scoped the query).

url is a best-effort constructed permalink
(`https://www.roksh.com/termek/{product_id}`), matching the same
unverified-permalink convention aldi_roksh_hu.py already uses for
shop.aldi.hu -- Penny has no dedicated storefront domain to link to, and
roksh.com's own in-app routes are Angular client-side (SPA), so no
server-rendered PDP exists to confirm a 200 against; this is a stable
identifier link, not guaranteed crawlable.

GOTCHA (same as aldi_roksh_hu): ROKSH is a personal-shopper platform, so
a margin on top of Penny's own shelf price is possible -- channel is
`marketplace`, not `supermarket`.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_PROVIDER_CODE = "PENNY-HU"
_CATEGORY_URL = (
    "https://shopservice.roksh.com/category/GetFullCategoryList"
    f"?providerCode={_PROVIDER_CODE}&isOwnWebshop=false"
)
_PRODUCTLIST_URL = (
    "https://shopservice.roksh.com/productlist/CategoryProductList"
    f"?providerCode={_PROVIDER_CODE}&progId={{prog_id}}&page=1&numberOfItems=500"
)


def _flatten_leaves(nodes: list) -> list:
    leaves = []
    for n in nodes or []:
        children = n.get("ChildList") or []
        if not children:
            prog_id = n.get("ProgID")
            if prog_id:
                leaves.append(prog_id)
        else:
            leaves.extend(_flatten_leaves(children))
    return leaves


class PennyRokshHuSpider(scrapy.Spider):
    name = "penny_roksh_hu"
    allowed_domains = ["roksh.com"]
    currency = "HUF"
    language = "hu"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_CATEGORY_URL, callback=self.parse_categories)

    def parse_categories(self, response):
        try:
            tree = response.json()
        except ValueError:
            logger.warning("penny_roksh_hu: bad category JSON")
            return
        leaves = _flatten_leaves(tree)
        logger.info("penny_roksh_hu: %d leaf categories", len(leaves))
        for prog_id in leaves:
            yield scrapy.Request(
                _PRODUCTLIST_URL.format(prog_id=prog_id),
                callback=self.parse_products,
                meta={"prog_id": prog_id},
            )

    def parse_products(self, response):
        if response.status != 200:
            # Some provider/leaf combinations 500 for reasons not
            # investigated this pass (see module docstring); skip rather
            # than fail the whole crawl.
            return
        try:
            payload = response.json()
        except ValueError:
            return
        for result in payload.get("ProductListResults") or []:
            pq = result.get("ProductQueryResultDto") or {}
            for row in pq.get("ProductList") or []:
                item = self._item(row)
                if item:
                    yield item

    def _item(self, row: dict):
        name = (row.get("productName") or "").strip()
        product_id = str(row.get("productID") or "")
        price = row.get("price")
        category = (row.get("category") or {}).get("categoryName")
        if not name or not product_id or price in (None, "", 0):
            return None
        return {
            "product_id": product_id,
            "product_name": name.replace("\n", " ").strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": bool(row.get("available", True)),
            "url": f"https://www.roksh.com/termek/{product_id}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
