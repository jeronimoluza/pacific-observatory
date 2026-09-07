"""Spider for Makro Pro Myanmar grocery and common-item categories."""

from ._makro_next_base import MakroNextCategorySpider


class MakroproMmSpider(MakroNextCategorySpider):
    name = "makropro_mm"
    allowed_domains = ["makropro.com.mm", "www.makropro.com.mm"]
    base_url = "https://www.makropro.com.mm"
    currency = "MMK"
    store_name = "Makro Pro Myanmar"
