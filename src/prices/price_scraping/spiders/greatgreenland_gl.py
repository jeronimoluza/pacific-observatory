"""
Great Greenland A/S -- https://www.greatgreenland.com/.

Greenland's national sealskin/fur tannery and fashion house -- coats,
footwear, jewelry and decorative skins. Site's own <html lang="da-DK">.
Standard WooCommerce Store API, DKK prices at currency_minor_unit=2,
confirmed live 2026-09-11.

Enumerability confirmed: x-wp-total=788 across 53 pages (per_page=15) --
the largest of the three Greenland candidates in this batch. page1 ids
distinct from page2 ids -- catalog paginates cleanly.

No catalog overlap with the country's other onboarded source
(pisiffik_gl, a department-store/electronics/furniture franchise
operator) -- different company, different product category (fur/leather
fashion goods).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class GreatgreenlandGlSpider(WooBaseSpider):
    name = "greatgreenland_gl"
    allowed_domains = ["greatgreenland.com"]
    currency = "DKK"
    language = "da"
    BASE_URL = "https://www.greatgreenland.com/wp-json/wc/store/v1/products"
