"""Guinea SIMPRIX — official regional ceiling prices for staple foods.

SIMPRIX (`simprix.gov.gn`) is the national price-monitoring portal of the
**Direction Nationale du Commerce Intérieur et de la Concurrence (DNCIC)**,
Ministère du Commerce, de l'Industrie et des PME. It publishes the legally
binding **prix plafonds** (maximum retail prices) for "denrées de première
nécessité et produits stratégiques", broken out by each of Guinea's 8
administrative regions.

WHY THIS IS `analytical_role: tariff`, NOT `official_avg`
    These are administered CEILING prices set by the regulator, not observed
    market averages. Labelling them `official_avg` would let a PPP basket
    treat a legal maximum as a measured transaction price. They belong in
    the administered-price layer alongside utility and fuel tariffs, even
    though the goods are COICOP division 01 food staples.

WHY A FETCHER, NOT A SPIDER
    Ten fixed items on a fixed regional grid, each with a stable COICOP
    mapping the source itself makes obvious ("RIZ IMPORTE 5% BRISURES
    50kg"). That is exactly the `source_curated` shape — there is nothing
    for the classifier to discover, and a per-item map is auditable.

ACCESS PATTERN (probed live 2026-09-05, no WAF, no auth)
    1. GET https://simprix.gov.gn/  -> brochure page whose only content link
       is the hashed public price route.
    2. GET /9e7d6b59065b43a81686e55819520ba0  -> "Liste générale des prix
       plafonds (CONAKRY)", 10 product cards, plus a Yii2 POST form
       carrying `_csrf` and a `<select name="cat">` of 8 region options
       whose values are opaque 48-hex-char zone ids.
    3. POST /f2c221bc67e676b877b898e8dd9a67fd with `_csrf`, `q=""` and
       `cat=<zone id>`  -> the same 10 cards repriced for that region.

    The zone `<select>` appears TWICE in the page (a desktop and a mobile
    copy) with the SAME option values but different label casing
    ("Conakry" / "CONAKRY"), so the zone list MUST be de-duplicated on the
    option value or every region is fetched and emitted twice.

    Verified live: all 8 regions return 10 cards each with genuinely
    different prices, e.g. RIZ IMPORTE 5% BRISURES 50kg —
    Conakry 280,000 / Kindia 292,200 / Mamou 297,833 / Faranah 302,500 /
    Kankan 308,900 / Boke 309,200 / Labe 309,600 / Nzerekore 314,917 GNF.
    A run in which two regions carry identical prices for every item is a
    failure signature (the POST silently fell back to the default page).

NUMBER FORMAT TRAP
    Prices render as "280.000 GNF / 50 KG" and "314.917 GNF / 50 KG". The
    "." is a THOUSANDS separator, not a decimal point — 314.917 is
    314,917 GNF, not 314.917 GNF. All digits are stripped of separators and
    read as a whole number of GNF. Sanity check: 280,000 GNF for 50 kg of
    imported rice is ~USD 0.65/kg, which is the right order of magnitude.

CADENCE / HISTORY
    The portal exposes only the CURRENT schedule — no archive of prior
    ceiling decisions was found. Per the skill's tariff-schedule guidance
    this fetcher snapshots the live schedule and stamps it with the run
    date under `period_kind: effective_from`, so successive runs build the
    series forward. `observation_date` is therefore the scrape date, not a
    publisher-stated effective date, which is recorded in `notes`.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Guinea"
_SOURCE_KEY = "simprix_prices_gin"
_BASE = "https://simprix.gov.gn"
_PRICE_PAGE = f"{_BASE}/9e7d6b59065b43a81686e55819520ba0"
_POST_ACTION = f"{_BASE}/f2c221bc67e676b877b898e8dd9a67fd"
_IDENT = ["source_key", "observation_date", "item_name", "unit", "subnational_area"]

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

# COICOP 2018 leaves for the 10 published staples. Written at onboarding
# because the source's own item list is fixed and unambiguous. An item that
# is NOT in this map is dropped with a warning rather than emitted with a
# null coicop_code.
_COICOP_MAP: dict[str, str] = {
    "RIZ IMPORTE 5% BRISURES 50KG": "01.1.1.1",
    "RIZ IMPORTE 25% BRISURES 50KG": "01.1.1.1",
    "RIZ IMPORTE 5% BRISURES 25KG": "01.1.1.1",
    "HUILE VEGETALE 20L": "01.1.5.2",
    "OIGNON 25 KG": "01.1.7.1",
    "POULET ENTIER IMPORTE 10 KG": "01.1.2.4",
    "CUISSE DE POULET IMPORTE 10 KG": "01.1.2.4",
    "SUCRE 50 KG": "01.1.8.1",
    "FARINE 50 KG": "01.1.1.2",
    "LAIT EN POUDRE 25KG": "01.1.4.3",
}

_CARD_RE = re.compile(
    r'<div class="product-details">(.*?)</div>\s*<!-- End \.product-details -->', re.S
)
_TITLE_RE = re.compile(r'<h3 class="product-title">\s*(.*?)\s*</h3>', re.S)
_PRICE_RE = re.compile(r'<span class="product-price">\s*(.*?)\s*</span>', re.S)
_CSRF_RE = re.compile(r'name="_csrf" value="([^"]+)"')
_OPTION_RE = re.compile(r'<option value="([0-9a-f]{20,})"\s*>([^<]+)</option>')
_TAG_RE = re.compile(r"<[^>]+>")


def _text(raw: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub("", raw)).strip()


def _parse_amount_unit(raw: str) -> tuple[float | None, str | None]:
    """'280.000 GNF / 50 KG' -> (280000.0, '50 KG'). '.' is a thousands sep."""
    m = re.match(r"\s*([\d.,\s]+?)\s*GNF\s*/\s*(.+?)\s*$", raw)
    if not m:
        return None, None
    digits = re.sub(r"[^\d]", "", m.group(1))
    if not digits:
        return None, None
    return float(digits), re.sub(r"\s+", " ", m.group(2)).strip()


def _parse_cards(html: str) -> list[tuple[str, float, str]]:
    out: list[tuple[str, float, str]] = []
    for card in _CARD_RE.findall(html):
        t = _TITLE_RE.search(card)
        p = _PRICE_RE.search(card)
        if not (t and p):
            continue
        name = _text(t.group(1))
        amount, unit = _parse_amount_unit(_text(p.group(1)))
        if not name or amount is None or amount <= 0:
            continue
        out.append((name, amount, unit or ""))
    return out


def fetch_simprix_prices_gin(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        logger.info("[%s] already snapshotted for cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    session = get_session()
    # The default research UA gets a flat 403 from this host; a plain Chrome
    # UA is enough (no TLS impersonation needed -- verified 2026-09-05).
    session.headers.update(_BROWSER_HEADERS)
    try:
        resp = session.get(_PRICE_PAGE, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] price page fetch failed: %s", _SOURCE_KEY, exc)
        return None

    csrf_m = _CSRF_RE.search(resp.text)
    if not csrf_m:
        logger.warning("[%s] no _csrf token on price page -- layout changed", _SOURCE_KEY)
        return None
    csrf = csrf_m.group(1)

    # The zone <select> is duplicated (desktop + mobile copies) with the same
    # option values and differently-cased labels -- de-dup on the value.
    zones: dict[str, str] = {}
    for value, label in _OPTION_RE.findall(resp.text):
        zones.setdefault(value, label.strip().title())
    if not zones:
        logger.warning("[%s] no region options found -- layout changed", _SOURCE_KEY)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    unmapped: set[str] = set()
    fingerprints: dict[str, str] = {}

    for zone_id, region in zones.items():
        try:
            page = session.post(
                _POST_ACTION,
                data={"_csrf": csrf, "q": "", "cat": zone_id},
                timeout=60,
            )
            page.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] region %s POST failed: %s", _SOURCE_KEY, region, exc)
            continue

        cards = _parse_cards(page.text)
        if not cards:
            logger.warning("[%s] region %s returned no cards", _SOURCE_KEY, region)
            continue
        fingerprints[region] = "|".join(f"{n}={a}" for n, a, _ in cards)

        for name, amount, unit in cards:
            code = _COICOP_MAP.get(re.sub(r"\s+", " ", name).upper())
            if not code:
                unmapped.add(name)
                continue
            row = {
                "observation_date": today.isoformat(),
                "period_kind": "effective_from",
                "country": _COUNTRY,
                "subnational_area": region,
                "source_key": _SOURCE_KEY,
                "coicop_code": code,
                "item_name": name,
                "price_local": amount,
                "currency": "GNF",
                "unit": unit,
                "source_url": _PRICE_PAGE,
                "notes": (
                    "DNCIC administered ceiling price (prix plafond); "
                    "observation_date is the snapshot date, the portal states "
                    "no effective-from date"
                ),
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if unmapped:
        logger.warning(
            "[%s] no COICOP mapping, rows dropped: %s", _SOURCE_KEY, sorted(unmapped)
        )
    if not rows:
        return None

    # Failure signature: every region returning the identical price vector
    # means the POST silently fell back to the default (Conakry) page.
    distinct = len(set(fingerprints.values()))
    if len(fingerprints) > 1 and distinct == 1:
        logger.warning(
            "[%s] all %d regions returned IDENTICAL prices -- region POST "
            "likely ignored; emitting anyway but treat as suspect",
            _SOURCE_KEY,
            len(fingerprints),
        )

    logger.info(
        "[%s] %d rows across %d regions (%d distinct price vectors, cutoff=%s)",
        _SOURCE_KEY,
        len(rows),
        len(fingerprints),
        distinct,
        cutoff,
    )
    return pd.DataFrame(rows)
