import re
from datetime import datetime, timezone
from urllib.parse import quote
import scrapy

class FrancosresortMenuSpider(scrapy.Spider):
    name = 'francosresort_menu'
    allowed_domains = ['francosresort.com', 'www.francosresort.com']
    start_urls = ['https://www.francosresort.com/']
    def parse(self, response):
        for i, card in enumerate(response.css('.dish-item, .menu-row')):
            name = ' '.join(card.css('.dish-name::text, .menu-row-name::text').getall()).strip()
            raw = card.css('.dish-price::text, .menu-row-price::text').get() or ''
            match = re.search(r'(?:Le|SLE)\s*([0-9][0-9,]*(?:\.[0-9]+)?)', raw, re.I)
            if name and match:
                product_id = f'{name.lower().replace(" ", "-")}-{i}'
                yield {'product_id': product_id, 'product_name': name, 'price': f'{float(match.group(1).replace(",", "")):.2f}', 'currency': 'SLE', 'category': 'restaurant menu', 'url': f'{response.url}#item={quote(product_id, safe="")}', 'language': 'en', 'scraped_at_utc': datetime.now(timezone.utc).isoformat()}
