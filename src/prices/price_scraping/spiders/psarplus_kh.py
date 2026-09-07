"""Spider for PsarPlus Cambodia grocery and common-item categories."""

from ._makro_next_base import MakroNextCategorySpider


class PsarplusKhSpider(MakroNextCategorySpider):
    name = "psarplus_kh"
    allowed_domains = ["psarplus.com", "www.psarplus.com"]
    base_url = "https://www.psarplus.com"
    currency = "USD"
    store_name = "PsarPlus"
