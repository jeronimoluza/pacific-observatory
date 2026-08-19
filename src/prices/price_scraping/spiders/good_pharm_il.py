"""Good Pharm (Israel, Bina/binaprojects.com) -- https://goodpharm.binaprojects.com/

Israel's 2014 Food Price Transparency Law statutory feed. Pharmacy chain --
genuine non-food win (divisions 05/06/13) from a statutory feed, not a
scraped storefront. Re-verified live 2026-08-06: 3,481 real items, e.g.
'GOOD PHARM - קיסמי שיניים מברישים' (dental floss picks) ILS 10.00,
'סנו ז'אוול - אקונומיקה לימון 2 ליטר' (Sano bleach 2L) ILS 10.00. Payload
is a zip archive despite the ".gz" filename -- handled by
_israel_transparency_base._extract_xml's magic-byte detection.
"""

from price_scraping.spiders._israel_transparency_base import BinaTransparencyBase


class GoodPharmIlSpider(BinaTransparencyBase):
    name = "good_pharm_il"
    bina_prefix = "goodpharm"
    bina_chain_id = "7290058197699"
