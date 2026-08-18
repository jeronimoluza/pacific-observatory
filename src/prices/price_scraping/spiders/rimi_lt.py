from price_scraping.spiders._rimi_baltic_base import RimiBalticBaseSpider


class RimiLtSpider(RimiBalticBaseSpider):
    name = "rimi_lt"
    allowed_domains = ["rimi.lt"]
    currency = "EUR"
    language = "lt"
    SEARCH_URL = "https://www.rimi.lt/e-parduotuve/lt/paieska"
    SEARCH_TERMS = [
        "pienas",
        "duona",
        "sūris",
        "kiaušiniai",
        "mėsa",
        "vištiena",
        "žuvis",
        "jogurtas",
        "sviestas",
        "cukrus",
        "miltai",
        "ryžiai",
        "makaronai",
        "kava",
        "arbata",
        "sultys",
        "vanduo",
        "alus",
        "vynas",
        "šokoladas",
        "sausainiai",
        "konservai",
        "daržovės",
        "vaisiai",
        "dešra",
    ]
