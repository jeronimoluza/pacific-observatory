from price_scraping.spiders._rimi_baltic_base import RimiBalticBaseSpider


class RimiLvSpider(RimiBalticBaseSpider):
    name = "rimi_lv"
    allowed_domains = ["rimi.lv"]
    currency = "EUR"
    language = "lv"
    SEARCH_URL = "https://www.rimi.lv/e-veikals/lv/meklesana"
    SEARCH_TERMS = [
        "piens",
        "maize",
        "siers",
        "olas",
        "gaļa",
        "vista",
        "zivis",
        "jogurts",
        "sviests",
        "cukurs",
        "milti",
        "rīsi",
        "makaroni",
        "kafija",
        "tēja",
        "sula",
        "ūdens",
        "alus",
        "vīns",
        "šokolāde",
        "cepumi",
        "konservi",
        "dārzeņi",
        "augļi",
        "desa",
    ]
