"""
Cyprus Retail Fuel Price Observatory (Ministry of Energy, Commerce and
Industry) — https://eforms.eservices.cyprus.gov.cy/MCIT/MCIT/PetroleumPrices.

Official government eForms ASP.NET portal (Παρατηρητήριο Λιανικών Τιμών
Καυσίμων), NOT a supermarket -- analytical_role=tariff. The results page
is a plain server-side form POST, no JS execution needed:

  1. GET the form to obtain a fresh `__RequestVerificationToken` (CSRF) and
     session cookie (Scrapy's cookie jar carries this automatically).
  2. POST the same URL once per fuel type (Entity.PetroleumType=1..5,
     Entity.StationCityEnum=All) -- the server returns the FULL results
     table for every station nationwide inline (no client pagination
     needed; footable is a display-only widget over the already-complete
     tbody). Verified live 2026-08-31: 304-316 stations per fuel type.

Verified live: Diesel (code 3) returned 316 rows; each row's "address"
column links to /PetroleumPrices/DisplayMap?coordinates=<lat>,<lon>, a
real per-station page (confirmed 200) used as this item's `url`.

Note: the UI's `_lang=en` toggle only translates chrome around the form --
the eForm itself (labels, station/company names) is Greek-only (its own
JS resource string admits this: "Η φόρμα δεν είναι διαθέσιμη στα
Αγγλικά" / "The form is not available in English") -- hence language="el".

Gotcha: the CSRF token is single-request-scoped to nothing in particular
here (the portal accepted the same token replayed across all 5 POSTs in
one session during testing), but re-fetch the GET each run rather than
hardcoding a token -- ASP.NET anti-forgery tokens are tied to the session
cookie, which is itself set only on that GET.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

FORM_URL = "https://eforms.eservices.cyprus.gov.cy/MCIT/MCIT/PetroleumPrices"
FUEL_TYPES = {
    "1": "Αμόλυβδη 95",  # Unleaded 95
    "2": "Αμόλυβδη 98",  # Unleaded 98
    "3": "Πετρέλαιο κίνησης",  # Diesel (automotive)
    "4": "Πετρέλαιο Θέρμανσης",  # Heating oil
    "5": "Κηροζίνη",  # Kerosene
}


class CyprusFuelObservatoryCySpider(scrapy.Spider):
    name = "cyprus_fuel_observatory_cy"
    allowed_domains = ["eforms.eservices.cyprus.gov.cy"]
    currency = "EUR"
    language = "el"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "COOKIES_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(f"{FORM_URL}?_lang=en", callback=self.parse_form)

    def parse_form(self, response):
        token = response.css(
            'input[name="__RequestVerificationToken"]::attr(value)'
        ).get()
        if not token:
            logger.warning(f"{self.name}: no CSRF token found on form page")
            return
        for code in FUEL_TYPES:
            yield scrapy.FormRequest(
                FORM_URL,
                formdata={
                    "__RequestVerificationToken": token,
                    "Entity.PetroleumType": code,
                    "Entity.StationCityEnum": "All",
                    "Entity.District": "",
                    "Entity.StationDistrict": "",
                },
                callback=self.parse_results,
                meta={"fuel_code": code},
                dont_filter=True,
            )

    def parse_results(self, response):
        fuel_code = response.meta["fuel_code"]
        fuel_label = FUEL_TYPES[fuel_code]
        scraped_at = datetime.now(timezone.utc).isoformat()
        rows = response.css("table#petroleumPriceDetailsFootable tbody tr")
        n = 0
        for row in rows:
            tds = row.css("td")
            if len(tds) < 5:
                continue
            company = " ".join(tds[0].css("::text").getall()).strip()
            station = " ".join(tds[1].css("::text").getall()).strip()
            district = " ".join(tds[3].css("::text").getall()).strip()
            price_text = " ".join(tds[4].css("::text").getall()).strip()
            if not station or not price_text:
                continue
            map_href = tds[2].css("a::attr(href)").get()
            base_url = response.urljoin(map_href) if map_href else response.url
            # A station's "station" column is often the OPERATING COMPANY's
            # legal name, not a per-branch label -- e.g. "PETROLINA
            # (HOLDINGS) PUBLIC LIMITED" owns dozens of distinct physical
            # stations across the island, so (company, station) text alone
            # collides. The map coordinates in the address link are the only
            # field that actually pins down one physical station -- use
            # those, not the row's free-text names, as the identity key.
            coords = None
            if map_href and "coordinates=" in map_href:
                coords = map_href.split("coordinates=", 1)[1]
            # A station selling multiple fuel grades reuses the same
            # DisplayMap?coordinates=... URL across fuel-type requests; the
            # DuplicationPipeline drops items on exact URL collision, so a
            # fuel-code fragment keeps one row per (station, fuel) pair
            # while the URL still resolves to the real per-station page.
            url = f"{base_url}#fuel={fuel_code}"
            name = f"{company} - {station}".strip(" -")
            yield {
                "product_id": f"{fuel_code}:{coords or (company + ':' + station)}",
                "product_name": name[:500],
                "category": fuel_label,
                "price": price_text,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "district": district or None,
                "scraped_at_utc": scraped_at,
            }
            n += 1
        logger.info(f"{self.name}: fuel={fuel_label} rows={n}")
