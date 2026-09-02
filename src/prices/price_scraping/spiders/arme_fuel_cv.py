"""
ARME (Agência Reguladora Multissetorial da Economia) — Cabo Verde regulated
maximum retail fuel prices — https://www.arme.cv/.

ARME, Cabo Verde's multisector economic regulator, fixes a nationwide
maximum retail price for fuel/gas every month (e.g. "ARME atualiza precos
maximos dos combustiveis para agosto 2026"). There is no JSON/table feed;
each decision is a Joomla news article under /index.php/noticia-geral,
interleaved with unrelated regulatory news (telecom, water, weekly
Brent-price PDF digests, consumer clarifications). The prose states every
fuel/gas price inline, e.g.:

  "a Gasolina passa a ser vendida a 168,10 ESC/L; o Gasoleo Normal, a
   157,60 ESC/L; ... o Gas Butano ... a granel; ... as garrafas de 12,5Kg,
   vendidas a 1.770,00 ESC; as de 6Kg, a 850,00 ESC; ..."

Verified this exact wording template holds for May/June/August 2026
(12/12 fields matched each time). Older notices (checked July 2019) use a
different template -- "ECV/L" instead of "ESC/L", "Fueloleo" instead of
"Fuel", "Electricidade" instead of "Eletricidade" -- and simply produce
zero regex matches, so they are silently skipped rather than mis-parsed;
this only shortens the walked history, it never emits a wrong number.

Pagination: /index.php/noticia-geral?start=N is Joomla's own listing
param, confirmed to advance (start=0/20/40 each returned a distinct set of
article ids). Candidate articles are filtered by slug: must mention both
"combustiv" and "preco" (catches "atualiza-precos-maximos-dos-combustiveis"
and the older "actualizacao-preco-combustiveis" spelling), and must not be
one of the weekly "relatorio-semanal" PDF digests or unrelated
"esclarece"/"hiace" articles that share the "combustiveis" word but carry
no price table.

Every row extracted from one article shares that article's URL. Per the
DuplicationPipeline's url-based dedup, all but the first would be silently
dropped -- each row's url is the article URL plus a '#<item-slug>'
fragment to keep it unique.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.arme.cv"
LISTING_PATH = "/index.php/noticia-geral"
STEP = 20
MAX_START = 1000  # site's own "last page" pagination link tops out ~972

_ARTICLE_RE = re.compile(r'href="(/index\.php/noticia-geral/(\d+)-([a-z0-9\-]+))"')

_SKIP_SLUG_RE = re.compile(
    r"relatorio-semanal|esclarece|hiace|consulta-publica|assembleia|"
    r"formacao|concurso|frequencia|emergencia|indicadores-estatisticos"
)
_FUEL_SLUG_RE = re.compile(r"combustiv.*preco|preco.*combustiv")

_NUM_RE = r"([\d]{1,3}(?:\.\d{3})*,\d{2})"

# (item_key, display name, unit, regex over the flattened article text)
_ITEMS = [
    (
        "gasolina",
        "Gasolina",
        "L",
        re.compile(r"[Gg]asolina[^0-9]{0,60}?" + _NUM_RE + r"\s*ESC/L"),
    ),
    (
        "gasoleo_normal",
        "Gasóleo Normal",
        "L",
        re.compile(r"Gas[oó]leo Normal[^0-9]{0,60}?" + _NUM_RE + r"\s*ESC/L"),
    ),
    (
        "gasoleo_eletricidade",
        "Gasóleo para Eletricidade",
        "L",
        re.compile(
            r"Gas[oó]leo (?:para )?Eletricidade[^0-9]{0,60}?" + _NUM_RE + r"\s*ESC/L"
        ),
    ),
    (
        "gasoleo_marinha",
        "Gasóleo Marinha",
        "L",
        re.compile(r"Gas[oó]leo Marinha[^0-9]{0,60}?" + _NUM_RE + r"\s*ESC/L"),
    ),
    (
        "petroleo",
        "Petróleo (querosene)",
        "L",
        re.compile(r"[Pp]etr[oó]leo,?\s*" + _NUM_RE + r"\s*ESC/L"),
    ),
    (
        "fuel_380",
        "Fuel 380",
        "kg",
        re.compile(r"Fuel 380[^0-9]{0,60}?" + _NUM_RE + r"\s*ESC/Kg"),
    ),
    (
        "fuel_180",
        "Fuel 180",
        "kg",
        re.compile(r"Fuel 180[^0-9]{0,60}?" + _NUM_RE + r"\s*ESC/Kg"),
    ),
    (
        "butano_granel",
        "Gás Butano a granel",
        "kg",
        re.compile(r"Butano[^0-9]{0,80}?" + _NUM_RE + r"\s*ESC/Kg a granel"),
    ),
    (
        "butano_12_5kg",
        "Gás Butano garrafa 12,5kg",
        "bottle_12.5kg",
        re.compile(r"12,5\s*Kg,?[^0-9]{0,30}?" + _NUM_RE),
    ),
    (
        "butano_6kg",
        "Gás Butano garrafa 6kg",
        "bottle_6kg",
        re.compile(r"(?:as )?de 6\s*Kg,\s*a\s*" + _NUM_RE),
    ),
    (
        "butano_3kg",
        "Gás Butano garrafa 3kg",
        "bottle_3kg",
        re.compile(r"(?:as )?de 3\s*Kg,\s*a\s*" + _NUM_RE),
    ),
    (
        "butano_55kg",
        "Gás Butano garrafa 55kg",
        "bottle_55kg",
        re.compile(r"(?:as )?de 55\s*Kg,?\s*" + _NUM_RE),
    ),
]

_BODY_RE = re.compile(
    r'itemprop="articleBody">(.*?)<div class="helix-social-share"', re.S
)


def _parse_pt_number(s: str) -> float:
    """'1.770,00' -> 1770.0 ; '96,90' -> 96.9 (Portuguese thousands/decimal)."""
    return float(s.replace(".", "").replace(",", "."))


class ArmeFuelCvSpider(scrapy.Spider):
    name = "arme_fuel_cv"
    allowed_domains = ["arme.cv"]
    currency = "CVE"
    language = "pt"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_articles: set[str] = set()

    async def start(self):
        yield scrapy.Request(
            f"{BASE_URL}{LISTING_PATH}",
            callback=self.parse_listing,
            errback=self.errback,
            meta={"start": 0},
        )

    def parse_listing(self, response):
        start = response.meta["start"]
        new_links = 0
        for full_path, article_id, slug in _ARTICLE_RE.findall(response.text):
            if article_id in self.seen_articles:
                continue
            self.seen_articles.add(article_id)
            if _SKIP_SLUG_RE.search(slug) or not _FUEL_SLUG_RE.search(slug):
                continue
            new_links += 1
            yield response.follow(
                full_path,
                callback=self.parse_article,
                errback=self.errback,
                meta={"article_id": article_id},
            )

        logger.info(f"{self.name}: start={start} new fuel-price links={new_links}")

        next_start = start + STEP
        if next_start <= MAX_START:
            yield scrapy.Request(
                f"{BASE_URL}{LISTING_PATH}?start={next_start}",
                callback=self.parse_listing,
                errback=self.errback,
                meta={"start": next_start},
            )

    def parse_article(self, response):
        body_match = _BODY_RE.search(response.text)
        if not body_match:
            logger.warning(f"{self.name}: no articleBody in {response.url}")
            return
        text = re.sub(r"<[^>]+>", " ", body_match.group(1))
        text = re.sub(r"&nbsp;|&amp;", " ", text)
        text = re.sub(r"\s+", " ", text)

        article_id = response.meta["article_id"]
        now = datetime.now(timezone.utc).isoformat()
        hits = 0
        for key, name, unit, pattern in _ITEMS:
            m = pattern.search(text)
            if not m:
                continue
            try:
                price = _parse_pt_number(m.group(1))
            except ValueError:
                continue
            hits += 1
            yield {
                "product_id": f"{article_id}-{key}",
                "product_name": f"{name} ({unit}), preço máximo ARME",
                "category": "fuel",
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": f"{response.url}#{key}",
                "language": self.language,
                "scraped_at_utc": now,
            }

        if hits < 4:
            logger.warning(
                f"{self.name}: only {hits}/{len(_ITEMS)} price fields matched in "
                f"{response.url}; likely an older/different-template notice, skipping "
                "any unmatched fields rather than guessing."
            )

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
