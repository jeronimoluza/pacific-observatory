"""
Dar Al-Amirat (Syria) -- https://daralamirat.shop/

Damascus beauty / personal-care e-commerce store on WordPress +
WooCommerce, with the public Store API open at
/wp-json/wc/store/v1/products.

WAF NOTE -- this is the reason the source was previously untried. The
site sits behind Hostinger's `hcdn` edge, which 403s (6192-byte stub) on
EVERY Chrome and Safari curl_cffi profile tried (chrome124, chrome120,
chrome131, safari17_0) but serves 200 on `firefox133`. A bare-curl or
Chrome-profile probe therefore reads as a hard block and is wrong. The
same lever recovered cloudmartsy.com and marketsyr.com in the same pass.

Because settings.py's RandomBrowserMiddleware overwrites
`request.meta["impersonate"]` on every request from the repo-wide
IMPERSONATE_BROWSERS pool (currently pinned to chrome120), WooBaseSpider's
IMPERSONATE_PROFILE alone is not enough here -- this spider narrows
IMPERSONATE_BROWSERS to firefox133 in custom_settings so the middleware
can only pick the profile that works.

MEASURED 2026-09-12 (firefox133): x-wp-total=358, x-wp-totalpages=18 at
per_page=20; page 1 vs page 2 product-id sets disjoint, zero overlap --
genuine pagination. Sample: "كاكازيان ماسك العين المضيء هالو كيتي زهري
للهالات 6غ" at 70.

CURRENCY: the Store API reports currency_code=SYP with
currency_minor_unit=0 and currency_suffix " ل.س" (e.g. price "70" ->
SYP 70). Read from the payload, not inferred.

CATALOG: oral care, deodorants, face masks, creams, hair care, body wash,
eye care -- COICOP 12.1 personal care, with a 06.x tail. Left wide
(coicop_codes unset) so the classifier assigns the leaf per product.

Page family: API.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class DaralamiratShopSpider(WooBaseSpider):
    name = "daralamirat_shop"
    allowed_domains = ["daralamirat.shop", "www.daralamirat.shop"]
    currency = "SYP"
    language = "ar"
    BASE_URL = "https://daralamirat.shop/wp-json/wc/store/v1/products"
    IMPERSONATE_PROFILE = "firefox133"

    custom_settings = {
        **WooBaseSpider.custom_settings,
        # RandomBrowserMiddleware unconditionally re-picks from this pool and
        # would otherwise clobber IMPERSONATE_PROFILE back to chrome120, which
        # this tenant's hcdn edge 403s.
        "IMPERSONATE_BROWSERS": ["firefox133"],
    }
