"""
Spider for SPAR Belgium (Colruyt Group) -- https://www.mijnspar.be/

mijnspar.be is an Adobe AEM content site, NOT a webshop: there is no cart,
no PDP, and no product catalogue. `sitemap.xml` (7,632 urls) is recipes,
news, jobs and store pages -- zero product urls -- and every guessed
`/shop`, `/product`, `/producten` path 404s. The ONLY price-bearing surface
on the domain is the weekly national promo list at `/promoties`, which the
AEM SPA hydrates from a component model.json (found via Playwright
network-trace + the `Allow: /content/spar/*.*.json$` line in robots.txt):

  GET /content/spar/nl/promoties/jcr:content/root/responsivegrid/
      responsivegrid/responsivegrid/filter_list_store_sp.model.json

  -> {"results": [{"promotion": {"promoTitle", "promoDescription",
       "promoPrice"/"normalPrice"/"unitPrice" as
       {"beforeDecimal","afterDecimal","empty"}, "unitOfUnitPrice",
       "pricePrefix", "label", "startDate", "endDate", "uuid"}, ...}]}

Verified live 2026-09-11: 43 results, 39 carrying a non-empty promoPrice.
The 4 without one are pure "X + Y gratis" mechanics with no money amount
(e.g. "conference peren Belgie", label "500 g + 500 g gratis") -- dropped.

PRICE SEMANTICS (this is the part that silently produces 2x errors):
`promoPrice` is the price of the WHOLE multi-buy bundle, and `pricePrefix`
carries the bundle size in free text -- "voor 2", "2 voor ", "4 voor ",
"voor 3", or null for a straight single-item promo. `normalPrice` is the
matching pre-discount bundle price. Confirmed on three records:
  - "Spar loempia's ... 1 kg"     promo 5,36 / normal 10,72 / prefix "voor 2"
  - "verse vijgen Turkije"        promo 0,99 / normal  1,98 / prefix "2 voor "
  - "Spar hotdogs ... 2 stuks"    promo 2,49 / normal  4,98 / prefix "2 voor "
In every case normalPrice == 2 x the single-unit shelf price, so the spider
divides BOTH amounts by the bundle size parsed out of `pricePrefix` and
emits a per-item price. `unit_price` / `unit_of_unit_price` (per kg / L /
st / fl) are carried through unchanged as the site publishes them.

All `afterDecimal` values observed are exactly 2 digits (43/43 records), so
the amount is assembled as f"{beforeDecimal}.{afterDecimal}"; anything that
is not 2 digits is dropped rather than guessed at.

The nl and fr trees serve the SAME promos (fr model.json is 398,665 bytes
vs nl 398,607 -- the identical list, translated), so only nl is walked, the
same way colruyt_be walks only the nl_BE sitemap shards.

DATA-QUALITY CAVEAT worth knowing downstream: a promo row is frequently a
GROUP of SKUs, not one SKU -- "gevulde pasta 400 g of gevulde gnocchi 280 g
naar keuze" ("... or ..., your choice"). The name is emitted exactly as the
site renders it (the classifier consumes the raw name), so those rows carry
an ambiguous quantity by construction.

No per-product url exists on this site at all, so `url` is keyed on the
promo's AEM uuid (`/promoties#<uuid>`) purely to keep DuplicationPipeline's
url-based dedup from collapsing the whole run into one row -- the same trap
documented on instashop_kz. It is NOT a browsable PDP, which is also why
this manifest carries no archive_prefix / archive_path_re.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_PROMO_JSON = (
    "https://www.mijnspar.be/content/spar/nl/promoties/jcr:content/root/"
    "responsivegrid/responsivegrid/responsivegrid/"
    "filter_list_store_sp.model.json"
)
_BUNDLE_RE = re.compile(r"\d+")


class MijnsparBeSpider(scrapy.Spider):
    name = "mijnspar_be"
    allowed_domains = ["mijnspar.be"]
    currency = "EUR"
    language = "nl"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 5,  # robots.txt declares crawl-delay: 5
        "DOWNLOAD_TIMEOUT": 60,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request(
            _PROMO_JSON,
            callback=self.parse_promos,
            headers={
                "Accept": "application/json",
                "Referer": "https://www.mijnspar.be/promoties",
            },
        )

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _amount(node):
        """{'beforeDecimal': '5', 'afterDecimal': '36'} -> 5.36, else None."""
        if not isinstance(node, dict) or node.get("empty"):
            return None
        before = node.get("beforeDecimal")
        after = node.get("afterDecimal")
        if before is None or after is None:
            return None
        before, after = str(before).strip(), str(after).strip()
        if not before.isdigit() or not after.isdigit() or len(after) != 2:
            logger.warning("mijnspar_be: odd amount %r.%r -- dropping", before, after)
            return None
        return float(f"{before}.{after}")

    @staticmethod
    def _bundle_size(price_prefix):
        """'voor 2' / '2 voor ' -> 2; None / no digit -> 1."""
        if not price_prefix:
            return 1
        m = _BUNDLE_RE.search(str(price_prefix))
        if not m:
            return 1
        n = int(m.group(0))
        return n if 1 <= n <= 12 else 1

    @staticmethod
    def _category(result):
        tags = (result.get("unfilteredLocalizedTags") or []) + (
            result.get("localizedTags") or []
        )
        names = [
            t.get("title")
            for t in tags
            if isinstance(t, dict) and "category" in str(t.get("tagID", ""))
        ]
        return " > ".join(n for n in names if n) or None

    # -- parse -----------------------------------------------------------

    def parse_promos(self, response):
        try:
            data = json.loads(response.text)
        except ValueError:
            logger.error("mijnspar_be: promo model.json is not JSON")
            return

        results = data.get("results") or []
        logger.info("mijnspar_be: %d promo results", len(results))
        scraped_at = datetime.now(timezone.utc).isoformat()
        emitted = 0

        for res in results:
            promo = res.get("promotion") or {}
            bundle_price = self._amount(promo.get("promoPrice"))
            if bundle_price is None:
                continue  # mechanics-only promo ("500 g + 500 g gratis")

            n = self._bundle_size(promo.get("pricePrefix"))
            price = round(bundle_price / n, 4)
            regular_bundle = self._amount(promo.get("normalPrice"))
            regular = round(regular_bundle / n, 4) if regular_bundle else None

            name = " ".join(
                str(p).strip()
                for p in (promo.get("promoTitle"), promo.get("promoDescription"))
                if p
            ).strip()
            if not name:
                continue

            uuid = str(promo.get("uuid") or res.get("uuid") or "")

            yield {
                "product_id": uuid or None,
                "product_name": name[:500],
                "category": self._category(res),
                "price": str(price),
                "currency": self.currency,
                "regular_price": str(regular) if regular is not None else None,
                "promo_bundle_price": str(bundle_price),
                "promo_bundle_size": n,
                "promo_label": (promo.get("label") or {}).get("title"),
                "unit_price": self._amount(promo.get("unitPrice")),
                "unit_of_unit_price": promo.get("unitOfUnitPrice"),
                "valid_from": promo.get("formattedStartDate"),
                "valid_to": promo.get("formattedEndDate"),
                "is_promotion": True,
                "url": f"https://www.mijnspar.be/promoties#{uuid}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            emitted += 1

        logger.info("mijnspar_be: emitted %d of %d results", emitted, len(results))
