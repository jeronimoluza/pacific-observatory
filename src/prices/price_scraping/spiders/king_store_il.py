"""King Store (Israel, Bina/binaprojects.com) -- https://kingstore.binaprojects.com/

Israel's 2014 Food Price Transparency Law statutory feed. Re-verified live
2026-08-06: 6,837 real items, e.g. 'פסטרמה מקסיקנית' (Mexican pastrami)
ILS 99.00. Payload is genuine gzip here (contrast good_pharm_il, which is
zip despite the same ".gz" extension).
"""

from price_scraping.spiders._israel_transparency_base import BinaTransparencyBase


class KingStoreIlSpider(BinaTransparencyBase):
    name = "king_store_il"
    bina_prefix = "kingstore"
    bina_chain_id = "7290058108879"
