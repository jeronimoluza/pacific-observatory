import re
from datetime import datetime, timezone
import scrapy

class SalonecartSpider(scrapy.Spider):
    name = 'salonecart'
    allowed_domains = ['salonecart.com']
    start_urls = ['https://salonecart.com/category/groceries']
    def parse(self, response):
        for i, card in enumerate(response.css('a[href*="/product/"]')):
            name = ' '.join(card.css('h3::text, h2::text').getall()).strip()
            match = re.search(r'SLE\s*([0-9][0-9,]*(?:\.[0-9]+)?)', ' '.join(card.css('::text').getall()), re.I)
            if name and match and float(match.group(1).replace(',', '')) > 0:
                yield {'product_id': card.attrib.get('href', '').rstrip('/').split('/')[-1], 'product_name': name, 'price': f'{float(match.group(1).replace(",", "")):.2f}', 'currency': 'SLE', 'category': 'groceries', 'url': response.urljoin(card.attrib['href']), 'language': 'en', 'scraped_at_utc': datetime.now(timezone.utc).isoformat()}
