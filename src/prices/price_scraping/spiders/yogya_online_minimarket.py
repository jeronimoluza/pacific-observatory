"""
Spider for Yogya Online Minimarket (Indonesia) -
minimarket.yogyaonline.co.id, the Yogya Group's minimarket storefront
(Java-wide convenience-store chain).

Server-rendered HTML category listing pages carry product name, SKU and
price inline - no PDP visits or JS rendering required. Category slugs are
discovered up front via the storefront's own `category-web/load` JSON
endpoint (called by the nav menu's JS); each category page returns ~24-42
product cards with no working `?page=` query param (identical results
regardless of page number), so breadth comes from walking categories, not
paginating within one.

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

_BASE = "https://minimarket.yogyaonline.co.id"

# Category slugs discovered from https://minimarket.yogyaonline.co.id/category-web/load
CATEGORIES = [
    "healthy-product-alat-kesehatan",
    "healthy-product-makanan-kesehatan",
    "healthy-product-minuman-kesehatan",
    "healthy-product-obatobatan",
    "healthy-product-pembalut-dan-popok-dewasa",
    "healthy-product-produk-higienis",
    "healthy-product-vitamin-dan-suplemen",
    "hobi-mainan",
    "hobi-otomotif",
    "hobi-rokok-dan-pemantik",
    "hot-deals-bonus-belanja",
    "hot-deals-buming",
    "hot-deals-daisabu",
    "hot-deals-harga-maraton",
    "hot-deals-pasti-hemat",
    "hot-deals-penawaran-istimewa",
    "hot-deals-produk-trending",
    "hot-deals-turun-harga",
    "jajanan-yomart-jajanan-makanan",
    "jajanan-yomart-yo-coffee",
    "kebutuhan-dapur-bahan-masakan",
    "kebutuhan-dapur-bahan-puding-dan-agaragar",
    "kebutuhan-dapur-bahan-roti-dan-kue",
    "kebutuhan-dapur-peralatan-dan-kebersihan-dapur",
    "kebutuhan-dapur-perlengkapan-dapur-dan-ruang-makan",
    "kebutuhan-ibu-bayi-dan-anak-kebutuhan-ibu-bayi-dan-anak-lainnya",
    "kebutuhan-ibu-bayi-dan-anak-makanan-bayi-dan-anak",
    "kebutuhan-ibu-bayi-dan-anak-pembersih-pakaian-dan-perlengkapan-anak",
    "kebutuhan-ibu-bayi-dan-anak-perlengkapan-makan-dan-minum-anak-dan-bayi",
    "kebutuhan-ibu-bayi-dan-anak-perlengkapan-mandi-dan-perawatan-anak-dan-bayi",
    "kebutuhan-ibu-bayi-dan-anak-popok-bayi-dan-anak",
    "kebutuhan-ibu-bayi-dan-anak-susu-formula-bayi-dan-anak",
    "kebutuhan-ibu-bayi-dan-anak-susu-ibu-hamil-dan-menyusui",
    "kebutuhan-kesehatan-alat-kesehatan",
    "kebutuhan-kesehatan-obatobatan",
    "kebutuhan-kesehatan-produk-higienis",
    "kebutuhan-kesehatan-vitamin-dan-suplemen",
    "kebutuhan-rumah-cairan-dan-bubuk-pembersih",
    "kebutuhan-rumah-electricity",
    "kebutuhan-rumah-pembasmi-hama-dan-serangga",
    "kebutuhan-rumah-pengharum-ruangan-dan-anti-lembab",
    "kebutuhan-rumah-perawatan-dan-pembersih-",
    "kebutuhan-rumah-perkakas",
    "kebutuhan-rumah-perlengkapan-mandi",
    "kebutuhan-rumah-perlengkapan-rumah",
    "kebutuhan-rumah-tisu",
    "kemasan-besar-food",
    "kemasan-besar-non-food",
    "makanan-bahan-makanan",
    "makanan-bakery",
    "makanan-makanan-instan",
    "makanan-makanan-ringan",
    "makanan-sarapan",
    "minuman-air-mineral",
    "minuman-minuman-instan",
    "minuman-minuman-ringan",
    "minuman-minuman-serbuk",
    "minuman-produk-olahan-susu",
    "minuman-sirup",
    "perawatan-wajah-dan-tubuh-beauty-is-you",
    "perawatan-wajah-dan-tubuh-deo-perfume",
    "perawatan-wajah-dan-tubuh-pembalut-dan-popok-dewasa",
    "perawatan-wajah-dan-tubuh-perawatan-dan-perlengkapan-pria",
    "perawatan-wajah-dan-tubuh-perawatan-gigi-dan-mulut",
    "perawatan-wajah-dan-tubuh-perawatan-rambut",
    "perawatan-wajah-dan-tubuh-perawatan-tubuh",
    "perawatan-wajah-dan-tubuh-perawatan-wajah",
    "perlengkapan-sekolah-dan-kantor-aksesoris",
    "perlengkapan-sekolah-dan-kantor-fancy",
    "perlengkapan-sekolah-dan-kantor-kantor",
    "perlengkapan-sekolah-dan-kantor-perlengkapan-makan-dan-minum-",
    "perlengkapan-sekolah-dan-kantor-sekolah",
    "pet-foods-makanan-anjing",
    "pet-foods-makanan-kucing",
    "pet-foods-peralatan-kebutuhan-hewan",
    "produk-import--makanan-import",
    "produk-import--minuman-import",
    "produk-import--produk-non-makanan-",
    "produk-segar-dan-beku-buah-dan-sayur",
    "produk-segar-dan-beku-daging-dan-ayam",
    "produk-segar-dan-beku-daily-food",
    "produk-segar-dan-beku-dessert-dan-juice",
    "produk-segar-dan-beku-makanan-beku",
    "produk-segar-dan-beku-makanan-laut",
    "produk-segar-dan-beku-susu-dan-olahannya",
    "produk-segar-dan-beku-telur",
    "yoa-dan-pasti-hemat-pasti-hemat",
    "yoa-dan-pasti-hemat-yoa-care",
    "yoa-dan-pasti-hemat-yoa-food",
    "yoa-dan-pasti-hemat-yoa-fresh",
    "yoa-dan-pasti-hemat-yoa-home",
    "yoa-dan-pasti-hemat-yoa-smart",
]

PRICE_RE = re.compile(r"^Rp\s*([0-9][0-9.,]*)$")


class YogyaOnlineMinimarketSpider(scrapy.Spider):
    name = "yogya_online_minimarket"
    allowed_domains = ["minimarket.yogyaonline.co.id"]
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
                f"{_BASE}/minimarket/{slug}/category",
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
            "yogya_online_minimarket: slug=%s yielded=%d",
            response.meta.get("slug"),
            yielded,
        )
