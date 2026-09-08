"""Liechtensteiner Brauhaus -- https://brauhaus.li/ (Schaan, Liechtenstein).

A genuinely domestic Liechtenstein producer: the country's own brewery
("Bier aus Liechtenstein seit 2007"), brewing in Schaan and selling direct.
Found by probing Liechtenstein drinks producers by domain after the wave-13
pass concluded the country's food/beverage options were exhausted at two
sources (ospelt_li, hofkellerei_li); it is a third, and it is the only
COICOP 02.1.1 (beer) source Liechtenstein has.

Standard WooCommerce Store API at /wp-json/wc/store/v1/products, fully open.
Prices are integer minor units with ``currency_minor_unit: 2`` and
``currency_code: "CHF"`` (Liechtenstein's currency), both handled by
``WooBaseSpider``: "350" -> CHF 3.50 for a 0.33l can, which matches the
rendered shop.

Small catalog by design -- 30 SKUs, the brewery's entire range: Spezialbier,
Club bier, Naturradler, an alcohol-free line, a caffeinated mate soft drink
(Viva Alpina), and a Liechtensteiner Single Malt Whisky. That spans COICOP
02.1.1 (beer), 02.1.3 (spirits) and 01.2.2 (soft drinks), so it is a WIDE
source by the narrowness rule (two different 3-digit classes) and
``coicop_codes`` stays unset for the classifier.

No same-shelf risk against Liechtenstein's other two food sources:
ospelt_li is meat/deli on Shopify and hofkellerei_li is the Princely wine
estate on a bespoke CMS -- disjoint products, disjoint id namespaces.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class BrauhausLiSpider(WooBaseSpider):
    name = "brauhaus_li"
    allowed_domains = ["brauhaus.li"]
    currency = "CHF"
    language = "de"
    BASE_URL = "https://brauhaus.li/wp-json/wc/store/v1/products"
