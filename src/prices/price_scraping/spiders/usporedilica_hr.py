"""
Spider for Usporedilica.hr — https://usporedilica.hr/.

Croatian multi-retailer grocery price-comparison aggregator. WordPress
custom theme; the product listing is a Vue SPA (`<Product></Product>`
mount points), so no price is present in the raw page HTML. The real data
lives behind a WP REST route: `https://usporedilica.hr/wp-json/custom/v1/
products/?shop=&sort=&page=N`, localized to the front end as
`window.MyScriptVars.rest_url` + a per-page-load nonce
(`window.MyScriptVars.nonce`, sent as the `X-WP-Nonce` header). The route
also 403s ("REST API access is restricted to usporedilica.hr") without a
same-origin `Referer`/`Origin` header -- curl_cffi with both headers plus
the nonce clears it.

Each entry in the `posts` array is itself an encrypted envelope, not a
plain object: base64(base64_ciphertext + "::" + hex_iv), AES-256-CBC,
PKCS7 padding, with the *hex key hardcoded in the shipped JS bundle*
(`wp-content/themes/usporedilica/dist/index.js`, function `decryptData`)
-- i.e. not a real secret, just client-side obfuscation. Decrypted
plaintext is HTML-entity-escaped JSON (`&quot;` etc.), so it needs an
`html.unescape()` pass before `json.loads`.

Verified live 2026-09-06: page=1 decrypts to 16 real products incl. "FAKS
900 ml GEL COLOR" EUR 1.70 (pricePerUnit 1.89/lit), "DET MERI MERINO
COLOUR 900ml" EUR 4.09. `max_pages` in the response was 3357 (~53,700
rows) -- this spider paginates through `max_pages` from the first
response rather than a hardcoded cap.
"""

import base64
import html
import json
import logging
from datetime import datetime, timezone

import scrapy
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

logger = logging.getLogger(__name__)

_BASE = "https://usporedilica.hr"
_API = f"{_BASE}/wp-json/custom/v1"
_AES_KEY = bytes.fromhex(
    "1c3c68317bafd990576dea4753a4672052dccced13f3cc4f49ff825a7b50998c"
)


def _decrypt(token: str):
    outer = base64.b64decode(token)
    ct_b64, iv_hex = outer.decode("utf-8").split("::")
    iv = bytes.fromhex(iv_hex)
    ct = base64.b64decode(ct_b64)
    decryptor = Cipher(algorithms.AES(_AES_KEY), modes.CBC(iv)).decryptor()
    pt = decryptor.update(ct) + decryptor.finalize()
    pt = pt[: -pt[-1]]  # strip PKCS7 padding
    return json.loads(html.unescape(pt.decode("utf-8")))


class UsporedilicaHrSpider(scrapy.Spider):
    name = "usporedilica_hr"
    allowed_domains = ["usporedilica.hr"]
    currency = "EUR"
    language = "hr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_BASE + "/", callback=self.parse_home)

    def parse_home(self, response):
        m = response.text.split('"nonce":"')
        if len(m) < 2:
            logger.error("usporedilica_hr: could not find nonce on homepage")
            return
        nonce = m[1].split('"')[0]
        yield self._api_request(page=1, nonce=nonce)

    def _api_request(self, page, nonce):
        return scrapy.Request(
            f"{_API}/products/?shop=&sort=&page={page}",
            callback=self.parse_page,
            meta={"page": page, "nonce": nonce},
            headers={
                "Referer": _BASE + "/",
                "Origin": _BASE,
                "X-WP-Nonce": nonce,
            },
        )

    def parse_page(self, response):
        page = response.meta["page"]
        nonce = response.meta["nonce"]
        data = json.loads(response.text)
        max_pages = data.get("max_pages", 0)
        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0
        for token in data.get("posts", []):
            try:
                obj = _decrypt(token)
            except Exception as exc:
                logger.warning(f"usporedilica_hr: decrypt failed: {exc}")
                continue
            count += 1
            yield {
                "product_id": str(obj.get("id")),
                "product_name": str(obj.get("title", "")).strip()[:500],
                "category": None,
                "price": obj.get("price"),
                "currency": self.currency,
                "available": True,
                "url": obj.get("link"),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"usporedilica_hr: page={page}/{max_pages} items={count}")

        if page < max_pages:
            yield self._api_request(page=page + 1, nonce=nonce)
