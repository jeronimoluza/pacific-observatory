"""Ta-Ta (Uruguay) -- https://www.tata.com.uy/. Full-line VTEX chain.

Custom domain 404s on /api/catalog_system/pub/... (Gatsby front-end only);
the tenant's myvtex.com origin serves the catalog directly (VTEX origin
bypass), account slug "tatauy".

Sales channel 1 (the API default) now indexes only ~220 SKUs; the storefront
catalog lives in sales channel 4, so every search request carries sc=4.
"""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class TataUySpider(VtexBaseSpider):
    name = "tata_uy"
    allowed_domains = ["tatauy.myvtex.com"]
    HOST = "tatauy.myvtex.com"
    currency = "UYU"
    language = "es"
    # ~2,150 leaves, most marketplace leaves empty: long item-less stretches.
    custom_settings = {
        **VtexBaseSpider.custom_settings,
        "CLOSESPIDER_TIMEOUT_NO_ITEM": 3600,
    }

    def _page_request(self, path, cat_name, from_):
        request = super()._page_request(path, cat_name, from_)
        return request.replace(url=request.url + "&sc=4")
