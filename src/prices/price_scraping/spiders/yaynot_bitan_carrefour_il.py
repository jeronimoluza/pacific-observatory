"""Yaynot Bitan / Carrefour Israel (PublishPrice) -- https://prices.carrefour.co.il/

Israel's 2014 Food Price Transparency Law statutory feed. Carrefour's
Israeli license holder (Electra Consumer Products, trading as Yaynot
Bitan/Carrefour). Re-verified live 2026-08-06: branch file
PriceFull7290055700007-001-002-*.gz, 6,241 real items, e.g. 'עגבניות שרי
שלמות' (whole cherry tomatoes) ILS 9.90. Payload is genuine gzip.
"""

from price_scraping.spiders._israel_transparency_base import (
    PublishPriceTransparencyBase,
)


class YaynotBitanCarrefourIlSpider(PublishPriceTransparencyBase):
    name = "yaynot_bitan_carrefour_il"
    site_infix = "carrefour"
    allowed_domains = ["prices.carrefour.co.il"]
