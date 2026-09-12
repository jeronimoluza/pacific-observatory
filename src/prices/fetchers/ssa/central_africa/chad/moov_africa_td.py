"""Moov Africa Tchad -- retail mobile prepaid bundle tariffs.

https://moov-africa.td/ -- one of Chad's two mobile operators. WordPress +
Elementor; the public "espace particulier" pages render every prepaid bundle
server-side as a grid of `div.forfait` cards, each holding an ordered run of
`div.elementor-widget-text-editor` widgets:

    Forfait            <- plan label, or a named plan ("Chabab Jour", "Monde 600")
    500 MB             <- what you get (data volume / minutes / SMS / bonus)
    *11*125#           <- the USSD activation code
    Durée : 1h         <- validity window
    150 FCFA           <- the price

Plain `requests` clears the host -- no WAF, no Playwright, no API needed.
The candidate triage had marked this NEEDS-CUSTOM-CRAWLER off a homepage
probe that found zero prices; the prices are one level down, on the
/espace-particulier/<offer>/ pages, which is why the homepage looked empty.

Seven offer pages are read: mobile data (kattir-internet), voice
(appel-moov-vers-moov), SMS (kattir-sms), mixed bundles (kattir-mix),
credit-bonus top-ups (kattir-ziada), social-network passes
(pass-reseaux-sociaux) and international minutes (offres-internationales).

Cross-page duplication is real and must be handled: a shared upsell block
(the `*11*125#` data ladder -- 1 GB / 7 jours / 1250 FCFA and friends)
renders on nearly every page, so 222 raw cards collapse to far fewer
distinct tariffs. Rows are deduped on (item_name, price, unit) with the
first page that showed a bundle winning, so the same tariff is not counted
once per page it happens to be advertised on.

`unit` carries the bundle's validity window (the thing the price buys), not
a billing period -- these are prepaid one-shot bundles, not subscriptions,
so there is no recurring charge to report.

All rows are COICOP 08.3.2.0 (mobile telecom services) -- single-value
_COICOP_MAP, coicop_classification: source_curated. Prices are integer XAF
(FCFA as rendered; Chad is the Central African CFA zone, so XAF not XOF).
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://moov-africa.td/espace-particulier"
_COUNTRY = "Chad"
_CURRENCY = "XAF"
_SOURCE_KEY = "td_moov_africa_tariffs"
_COICOP = "08.3.2.0"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]

# Offer page slug -> the bundle family it advertises.
_PAGES = {
    "kattir-internet": "Internet",
    "appel-moov-vers-moov": "Appel",
    "kattir-sms": "SMS",
    "kattir-mix": "Mix",
    "kattir-ziada": "Ziada",
    "pass-reseaux-sociaux": "Pass reseaux sociaux",
    "offres-internationales": "International",
}

_PRICE_RE = re.compile(r"([\d][\d\s.,]*)\s*FCFA", re.IGNORECASE)
_DURATION_RE = re.compile(r"Dur[ée]e\s*:?\s*(.+)", re.IGNORECASE)


def _to_amount(raw: str) -> float | None:
    cleaned = raw.replace("\xa0", "").replace(" ", "").replace(",", "").replace(".", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


def _parse_card(card) -> tuple[str, float, str] | None:
    """-> (offer description, price, validity) for one .forfait card."""
    texts = [
        t.get_text(" ", strip=True)
        for t in card.select("div.elementor-widget-text-editor")
    ]
    texts = [re.sub(r"\s+", " ", t).strip() for t in texts if t and t.strip()]
    price = None
    validity = None
    parts: list[str] = []
    for t in texts:
        m = _PRICE_RE.search(t)
        if m and price is None:
            price = _to_amount(m.group(1))
            continue
        d = _DURATION_RE.search(t)
        if d:
            validity = d.group(1).strip()
            continue
        if t.startswith("*") or t.startswith("#"):
            # USSD activation code, not part of the product identity.
            continue
        parts.append(t)
    if price is None or not parts:
        return None
    return " ".join(parts), price, validity or "unspecified"


def fetch_td_moov_africa_tariffs(cutoff: date) -> pd.DataFrame | None:
    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        logger.info(
            "moov_africa_td: obs_date %s <= cutoff %s — no new rows", obs_date, cutoff
        )
        return None

    session = get_session()
    scrape_ts = get_scrape_ts()
    rows: list[dict] = []
    seen: set[tuple[str, float, str]] = set()

    for slug, family in _PAGES.items():
        url = f"{_BASE}/{slug}/"
        try:
            resp = session.get(url, timeout=45)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - one bad page must not kill the run
            logger.warning("moov_africa_td: %s failed (%s)", url, exc)
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("div.forfait")
        if not cards:
            logger.warning("moov_africa_td: no .forfait cards on %s", url)
            continue
        for card in cards:
            parsed = _parse_card(card)
            if not parsed:
                continue
            offer, price, validity = parsed
            key = (offer.lower(), price, validity.lower())
            if key in seen:
                # Same bundle re-advertised on another offer page.
                continue
            seen.add(key)
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "subnational_area": None,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP,
                "item_name": f"Moov Africa Tchad {family} — {offer}",
                "price_local": price,
                "currency": _CURRENCY,
                "unit": validity,
                "source_url": url,
                "notes": None,
                "scrape_ts": scrape_ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        logger.warning("moov_africa_td: no tariff rows extracted")
        return None
    return pd.DataFrame(rows)
