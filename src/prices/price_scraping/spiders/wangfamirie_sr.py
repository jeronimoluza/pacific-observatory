"""
Wang Famirie (Suriname diaspora grocery/parcel shipping) -- https://wangfamirie.com/.

"Boodschappen en Paketten voor Suriname" -- a Netherlands-run webshop where
customers order groceries and parcels online for delivery to family in
Suriname ("ontvang binnen 4 dagen" -- receive within 4 days). WooCommerce
Store API confirmed live 2026-09-11
(https://wangfamirie.com/wp-json/wc/store/v1/products), 3,601 SKUs.
Real grocery categories present and dominant by SKU count: DRANKEN
(beverages, 211), ONTBIJT (breakfast, 203), SAUS EN MARINADE (195),
ZOET & SNACKS (156), VLEES/meat (154, incl. Kip/chicken 46, Varken/pork 42,
Rund/beef 22, Zoutvlees/salted meat 10), ZUIVEL/dairy (95), GROENTEN/
vegetables (75), THEE & KOFFIE (49), VIS/fish (32), KRUIDEN/herbs (30),
FRUIT (22), DIEPVRIES/frozen (21), BROOD/bread (14) -- alongside household/
personal-care (TOILETARTIKELEN, HYGIENE), BABY, PHARMA and SCHOOL lines.
currency_code=EUR, minor_unit=2 (prices are minor-unit integers, e.g. raw
"2630" -> EUR 26.30 for a school backpack; WooBaseSpider divides by
10**currency_minor_unit).

NOT the same catalog as avoda_sr / now2su.com (HEM Suriname N.V.'s SRD/EUR
storefronts) or surishop.nl -- independent operator ("Vincent Fanny",
per the site's author byline), distinct product names/brands (Caribbean
diaspora brands: Pacifico, Chitra, Mar-Jac) and a different backend. Channel
tagged `supermarket` on the same basis as avoda_sr: first-party general
grocery webshop with a real full-depth food department, mixed with
household/personal-care lines (an online-delivery basket skewing away from
fresh is expected and not evidence against the tag).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class WangfamirieSrSpider(WooBaseSpider):
    name = "wangfamirie_sr"
    allowed_domains = ["wangfamirie.com"]
    currency = "EUR"
    language = "nl"
    BASE_URL = "https://wangfamirie.com/wp-json/wc/store/v1/products"
