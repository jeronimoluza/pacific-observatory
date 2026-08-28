from price_scraping.spiders._koro_base import KoroBaseSpider


class KoroPtSpider(KoroBaseSpider):
    name = "koro_pt"
    allowed_domains = ["bff.koro.com"]
    currency = "EUR"
    language = "pt"
    ACCESS_KEY = "SWSCEEZONWLSY0HADK9TZVHDYW"
    DOMAIN = "www.koro.com/pt"
