"""
Spider for Geant Drive Tunis City -- https://www.geantdrive.tn/tunis-city/.

PrestaShop storefront (FreshFood theme) for Geant Tunisie's hypermarket
click-and-collect arm ("Geant Drive"). geant.tn itself (the corporate site)
has no catalog -- it links out to this separate geantdrive.tn domain, which
IS a full online supermarket ("faire ses courses chez Geant Drive"). The
homepage cert (Sectigo DV, valid to 2026-11-20) fails curl_cffi's default
verification because of a missing intermediate in the served chain -- not
an expired/hijacked-domain signature, just an incomplete chain; Scrapy's
default context factory does not perform certificate validation so no
special handling is needed here.

Full hypermarket taxonomy confirmed live 2026-09-01 (epicerie-et-boissons,
le-frais incl. fruits/legumes/boucherie/poissonnerie/creamerie, parfumerie-
hygiene-et-entretien, maison, high-tech, mode, bebe, animalerie -- ~100
leaf categories). Standard PrestaShop `[itemtype="http://schema.org/
Product"]` microdata per card (48/page sampled on category 161-legumes),
so the shared PrestashopBaseSpider crawler applies unmodified.

This is a single-store scope (Tunis City pickup point). Geant Drive is a
multi-store PrestaShop tenant (the site also serves at least an "Azur City"
pickup point per the corporate site's copy) -- only tunis-city is scraped
to avoid onboarding what could be a near-duplicate catalog under a second
storefront path; a future pass could sample azur-city and compare product
overlap before deciding whether it is a second source or the same shelf.

Cert fix, scoped to this spider only (does NOT touch `_prestashop_base.py`,
per the rule against changing shared base-spider behaviour): the server
sends only its leaf cert, no intermediate (`openssl s_client -showcerts`
returns exactly one CERTIFICATE block), so curl_cffi cannot build a path to
the trusted root. Fix is to vendor the missing intermediate
(`_geant_drive_tn_chain.pem`, fetched from the leaf cert's own AIA "CA
Issuers" URI: http://crt.sectigo.com/SectigoPublicServerAuthenticationCADVR36.crt)
and pass a combined certifi+intermediate bundle via `impersonate_args=
{"verify": ...}` -- not `verify=False` -- precedent: mojsupermarket_me.py,
fetchers/sar/south_asia/bangladesh/_tcb_gov_bd_chain.pem. Since every
request in this crawl is built inside the shared base class, the bundle is
injected via a downloader middleware registered ONLY in this spider's own
`custom_settings`, not in settings.py or the base class.
"""

import re
import tempfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin

import certifi

from price_scraping.spiders._prestashop_base import PrestashopBaseSpider

_CHAIN_PEM = Path(__file__).with_name("_geant_drive_tn_chain.pem")
_PRICE_NUM_RE = re.compile(r"\d[\d\s.,]*\d|\d")
_JUNK_H1_RE = re.compile(r"Abonnez|Paiement|Veuillez choisir", re.IGNORECASE)


def _normalize_tnd_price(raw: str) -> str | None:
    """TND-aware price cleaner, overriding `_prestashop_base.normalize_price`
    for this spider only (not touching the shared function -- see module
    docstring). TND always displays exactly 3 decimal digits (millimes),
    e.g. "14,100 DT" = 14.100 TND. The shared heuristic treats a lone
    separator followed by a 3-digit group as a THOUSANDS separator (correct
    for 2-decimal currencies, wrong here) -- confirmed live: "14,100 DT" was
    mis-parsed as 14100 TND (~4500 USD for an inflatable pool toy) instead
    of the correct 14.100 TND (~4.50 USD). This mirrors the LYD/JOD/TND
    3-decimal trap documented for this sweep.
    """
    if not raw:
        return None
    m = _PRICE_NUM_RE.search(raw)
    if not m:
        return None
    s = re.sub(r"\s", "", m.group(0))
    n_seps = s.count(",") + s.count(".")
    if n_seps == 1:
        sep = "," if "," in s else "."
        integer_part, frac = s.split(sep)
        if len(frac) == 3:
            s = f"{integer_part}.{frac}"
        else:
            s = integer_part + frac
    elif n_seps > 1:
        if s.rindex(",") > s.rindex("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    try:
        float(s)
    except ValueError:
        return None
    return s


@lru_cache(maxsize=1)
def _ca_bundle() -> str:
    bundle = Path(tempfile.gettempdir()) / "geant_drive_tn_ca_bundle.pem"
    bundle.write_bytes(
        Path(certifi.where()).read_bytes() + b"\n" + _CHAIN_PEM.read_bytes()
    )
    return str(bundle)


class _InjectCaBundleMiddleware:
    """Scoped to geant_drive_tn only via this spider's custom_settings --
    supplies the missing intermediate cert for every request to this
    domain's incomplete TLS chain (see module docstring)."""

    def process_request(self, request, spider):
        request.meta.setdefault("impersonate_args", {})["verify"] = _ca_bundle()
        return None


class GeantDriveTnSpider(PrestashopBaseSpider):
    name = "geant_drive_tn"
    allowed_domains = ["geantdrive.tn"]
    currency = "TND"
    language = "fr"
    HOME_URL = "https://www.geantdrive.tn/tunis-city/"

    custom_settings = {
        **PrestashopBaseSpider.custom_settings,
        "DOWNLOADER_MIDDLEWARES": {
            **PrestashopBaseSpider.custom_settings.get("DOWNLOADER_MIDDLEWARES", {}),
            f"{__name__}._InjectCaBundleMiddleware": 100,
        },
    }

    def _items(self, c, response):
        """Override of `_prestashop_base._items` for this spider only --
        identical card/name/id/url extraction, but routes price text
        through `_normalize_tnd_price` instead of the shared
        `normalize_price` (see module docstring for why). No `div.remise`
        payment-discount markup exists on this theme (confirmed live), so
        `_remise_variants` is not invoked."""
        name = c.xpath('string(.//*[@itemprop="name"])').get()
        name = re.sub(r"\s+", " ", name).strip() if name else None
        if not name:
            return
        url = c.xpath(
            '(.//*[@itemprop="name"]/ancestor::a[1]/@href | .//*[@itemprop="name"]//a/@href)[1]'
        ).get()
        product_id = (
            c.attrib.get("data-id-product")
            or c.css("[data-id-product]::attr(data-id-product)").get()
        )
        if not product_id and url:
            m = re.search(r"/(\d+)-[a-z0-9\-]+\.html", url)
            product_id = m.group(1) if m else None
        if not product_id:
            return
        price_text = (
            c.css('[itemprop="price"]::text').get() or c.css(".price::text").get()
        )
        price = _normalize_tnd_price(price_text) if price_text else None
        if not price:
            return
        try:
            if float(price) <= 0:
                return  # a price of 0 (or negative) is not an observation
        except ValueError:
            return
        category = self._category_label(response)
        if category and _JUNK_H1_RE.search(category):
            # this theme's real category pages carry the true title as the
            # FIRST <h1> text node (confirmed live: "Plage et plein air",
            # "Legumes"), but pages with no real title (e.g. /brand/*
            # manufacturer listings, and the home "category" itself) fall
            # straight through to a shared footer newsletter-signup <h1>
            # ("Abonnez-vous a notre newsletter") -- never a real category.
            category = None
        full_url = urljoin(response.url, url) if url else response.url
        if not category and full_url:
            # fall back to the product's OWN url slug
            # (/<cat-slug>/<id>-<name>.html) -- present on every PDP
            # regardless of which listing page (real or fallback) found it.
            cm = re.search(r"/([a-z0-9\-]+)/\d+-[a-z0-9\-]+\.html", full_url)
            if cm:
                category = cm.group(1).replace("-", " ")
        yield {
            "product_id": str(product_id),
            "product_name": name[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": full_url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
