from price_scraping.spiders._rimi_baltic_base import RimiBalticBaseSpider


class RimiEeSpider(RimiBalticBaseSpider):
    name = "rimi_ee"
    allowed_domains = ["rimi.ee"]
    currency = "EUR"
    language = "et"
    SEARCH_URL = "https://www.rimi.ee/epood/ee/otsing"
    SEARCH_TERMS = [
        "piim",
        "leib",
        "juust",
        "munad",
        "liha",
        "kana",
        "kala",
        "jogurt",
        "või",
        "suhkur",
        "jahu",
        "riis",
        "pasta",
        "kohv",
        "tee",
        "mahl",
        "vesi",
        "õlu",
        "vein",
        "šokolaad",
        "küpsised",
        "konservid",
        "köögiviljad",
        "puuviljad",
        "vorst",
    ]
