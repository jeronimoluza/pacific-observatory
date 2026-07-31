"""
Spider for Yogya Online Supermarket (Indonesia) -
supermarket.yogyaonline.co.id, the Yogya Group's supermarket storefront
(same operator as the minimarket.yogyaonline.co.id convenience-store
subdomain, sibling `yogya_online_minimarket` spider).

The homepage's flash-sale carousel needs a delivery-address/store context,
but the category listing pages at /supermarket/<slug>/category are plain
server-rendered HTML with product name, SKU and price inline - no login,
store-select, or JS rendering required. Category slugs are discovered up
front via the storefront's own `category-web/load` JSON endpoint (called by
the nav menu's JS; requires a same-origin Referer or it 200s with an
AntiBot-rejection body). Each category page returns ~30-42 product cards
with no working `?page=` query param.

Price cards can carry a struck-through "before" price inside `.product-promo`
(wrapped in `<del>`) alongside the current price inside `.mt-auto
.product-price`; scoping the price selector to `.mt-auto` avoids picking up
the stale promo price.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://supermarket.yogyaonline.co.id"

# Category slugs discovered from
# https://supermarket.yogyaonline.co.id/category-web/load (Referer required)
CATEGORIES = [
    "bakery-kue-kering",
    "bakery-roti-dan-pastry",
    "cairan-dan-bubuk-pembersih-deterjen-bubuk",
    "cairan-dan-bubuk-pembersih-disinfectant",
    "cairan-dan-bubuk-pembersih-lainlain",
    "cairan-dan-bubuk-pembersih-pelicin-pakaian",
    "cairan-dan-bubuk-pembersih-pencuci-piring",
    "cairan-dan-bubuk-pembersih-pengharum-kamar-mandi",
    "cairan-dan-bubuk-pembersih-pengharum-ruangan",
    "fresh-buah-sayur-buahbuahan",
    "fresh-buah-sayur-sayursayuran",
    "fresh-telur",
    "healthy-produk-makanan-sehat",
    "hobi-hewan-peliharaan-kucing",
    "hobi-perkakas-dan-alat-pertukangan",
    "home-and-living-mebel-dan-tempat-penyimpanan",
    "home-and-living-tisu-tisu-wajah",
    "hot-deals-flash-sale-31-02",
    "hot-deals-produk-rekomendasi",
    "hot-deals-produk-terbaru",
    "hot-deals-promo-minggu-ini-daisabu",
    "hot-deals-promo-minggu-ini-harga-maraton",
    "ibu-bayi-dan-anak-makanan-bayi",
    "ibu-bayi-dan-anak-susu-anak",
    "ibu-bayi-dan-anak-susu-bayi",
    "ibu-bayi-dan-anak-susu-ibu-hamil",
    "lifestyle-lainlain",
    "lifestyle-mainan",
    "lifestyle-pakaian",
    "lifestyle-perlengkapan-ibadah",
    "makanan-sarapan-roti",
    "minuman-air-mineral",
    "minuman-kental-manis",
    "minuman-minuman-ringan",
    "minuman-minuman-serbuk",
    "minuman-sirup",
    "official-store-yoa-pasti-hemat-yoa-fresh",
    "perawatan-tubuh-kebutuhan-manula",
    "perawatan-tubuh-kosmetik",
    "perawatan-tubuh-parfum",
    "perawatan-tubuh-perawatan-tubuh-treatment-wajah",
    "perawatan-tubuh-perawatan-wajah-treatment-wajah",
    "perawatan-tubuh-perawatan-rambut-shampoo",
    "perlengkapan-sekolah-dan-kantor-fancy",
    "perlengkapan-sekolah-dan-kantor-seasonal",
    "perlengkapan-sekolah-dan-kantor-sekolah-alat-tulis",
    "perlengkapan-sekolah-dan-kantor-tas",
    "produk-import-makanan-import-mie-pasta",
    "produk-import-makanan-import-sarapan",
    "produk-import-minuman-import",
    "produk-non-halal-makanan-non-halal",
    "yogya-elektronik-home-appliances",
    "yogya-elektronik-tv",
]

PRICE_RE = re.compile(r"^Rp\s*([0-9][0-9.,]*)$")


class YogyaOnlineSupermarketSpider(scrapy.Spider):
    name = "yogya_online_supermarket"
    allowed_domains = ["supermarket.yogyaonline.co.id"]
    currency = "IDR"
    language = "id"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1,
    }

    async def start(self):
        for slug in CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/supermarket/{slug}/category",
                callback=self.parse_listing,
                meta={"slug": slug},
            )

    def parse_listing(self, response):
        breadcrumb = [
            t.strip()
            for t in response.css(
                "ol.breadcrumb li.breadcrumb-item a::text, "
                "ol.breadcrumb li.breadcrumb-item.active::text"
            ).getall()
            if t.strip() and t.strip() != "Home"
        ]
        category = " > ".join(breadcrumb) if breadcrumb else None

        cards = response.css(".product-item[data-object-id]")
        scraped_at = datetime.now(timezone.utc).isoformat()
        yielded = 0
        for card in cards:
            object_id = card.attrib.get("data-object-id", "")
            product_id = object_id.split("_")[0] if object_id else None

            name = card.css(".product-name .ellipsis-me::attr(title)").get()

            price = None
            for t in card.css(".mt-auto .product-price::text").getall():
                m = PRICE_RE.match(t.strip())
                if m:
                    price = m.group(1).replace(".", "").replace(",", "")
                    break

            href = card.css(".product-image-container::attr(href)").get()

            if not name or not price:
                continue

            yield {
                "product_id": product_id,
                "product_name": name.strip(),
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": response.urljoin(href) if href else response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            yielded += 1
        logger.info(
            "yogya_online_supermarket: slug=%s yielded=%d",
            response.meta.get("slug"),
            yielded,
        )
