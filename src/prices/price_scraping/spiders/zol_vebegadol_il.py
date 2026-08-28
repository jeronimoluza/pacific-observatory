"""Zol VeBegadol (Israel, Bina/binaprojects.com) -- https://zolvebegadol.binaprojects.com/

Israel's 2014 Food Price Transparency Law statutory feed. Re-verified live
2026-08-06: 2,861 real items, e.g. 'חלה רגילה קלועה/מרובעת' (braided challah
bread) ILS 6.60. Payload is a zip archive despite the ".gz" filename.
"""

from price_scraping.spiders._israel_transparency_base import BinaTransparencyBase


class ZolVebegadolIlSpider(BinaTransparencyBase):
    name = "zol_vebegadol_il"
    bina_prefix = "zolvebegadol"
    bina_chain_id = "7290058173198"
