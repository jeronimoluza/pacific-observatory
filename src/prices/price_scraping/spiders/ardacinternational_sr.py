"""
Ardac International (Suriname) -- https://ardacinternational.sr/.

Standard WooCommerce Store API. Mixed corporate-supply catalog: workwear
/ textiles ('Werkkleding'), promotional awards/trophies ('Awards'),
outdoor/tools ('Tools & Outdoor'), paper bags ('Papieren Tassen'). Reads
as a promotional-products / corporate-supplies wholesaler rather than a
single-category consumer retailer -- classified 'other' (no enum value
fits a mixed workwear+awards+packaging catalog; 'fashion' would
misrepresent the awards/bags share of the catalog).

Verified live 2026-09-11: x-wp-total=183, x-wp-totalpages=183 at
per_page=1 (i.e. 183 products, ~10 pages at per_page=20). Page 1 vs page
2 (per_page=20) returned disjoint product-id sets, zero overlap --
genuine pagination. Small catalog by design (B2B corporate supplier);
breadth of distinct products across textiles/awards/tools/packaging is
useful here per the wave-5 brief even though the catalog is small.

Currency: Store API reports currency_code=SRD -- matches Suriname's
country currency. currency_minor_unit=2 (e.g. price "85000" -> SRD
850.00).

Note: permalinks resolve on www.ardacinternational.sr (the bare domain
also serves the Store API directly).

Page family: API (Store API JSON; permalinks are real PDP URLs but never
fetched by this spider).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class ArdacinternationalSrSpider(WooBaseSpider):
    name = "ardacinternational_sr"
    allowed_domains = ["ardacinternational.sr", "www.ardacinternational.sr"]
    currency = "SRD"
    language = "nl"
    BASE_URL = "https://ardacinternational.sr/wp-json/wc/store/v1/products"
