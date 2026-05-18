"""Tolls.eu fuel chart API — used for ECA microstates (Monaco, Liechtenstein, San Marino).

The page at https://www.tolls.eu/fuel-prices renders a historical fuel-price
chart by POSTing to ``/fetch/fuel.php`` with a per-session CSRF token. The
``iso3=<ISO3>`` parameter returns weekly history for a single country since
2023-01-02 — covering microstates that are not in any other source.

Endpoint behaviour:
  POST https://www.tolls.eu/fetch/fuel.php
  body: iso3=<ISO3>&fuel=<gasoline|diesel|lpg>&lang=en&token=<64hex>
  → {"values": [{"x": "YYYY-MM-DD", "y": <float|"">}, ...]}

The token is a per-session, page-rendered string (likely SHA-256). We harvest
it via a single headless Playwright load, then drive subsequent POSTs through
plain ``requests`` reusing the same cookies — cheap and parallelisable.

Per-country coverage (verified 2026-05-12):
  - MCO Monaco       — gasoline + diesel populated, LPG empty
  - LIE Liechtenstein— gasoline + diesel populated, LPG empty
  - SMR San Marino   — gasoline + diesel + LPG all populated
"""

import json
import logging
import re
from datetime import date, datetime

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_FUEL_PRICES_URL = "https://www.tolls.eu/fuel-prices"
_ENDPOINT = "https://www.tolls.eu/fetch/fuel.php"
_FUELS = ("gasoline", "diesel", "lpg")

_PRODUCT_LABELS = {
    "gasoline": "Gasoline 95",
    "diesel": "Diesel",
    "lpg": "LPG",
}

# Per-microstate metadata (currency, source_key).
_COUNTRIES: dict[str, dict] = {
    "mc": {
        "name": "Monaco",
        "iso3": "MCO",
        "currency": "EUR",
        "source_key": "tolls_mc_weekly",
        "unit": "L",
    },
    "li": {
        "name": "Liechtenstein",
        "iso3": "LIE",
        "currency": "CHF",
        "source_key": "tolls_li_weekly",
        "unit": "L",
    },
    "sm": {
        "name": "San Marino",
        "iso3": "SMR",
        "currency": "EUR",
        "source_key": "tolls_sm_weekly",
        "unit": "L",
    },
}


def _harvest_session() -> tuple[requests.Session, str]:
    """One headless Playwright load → capture CSRF token + cookies.

    Returns a ``requests.Session`` with the cookies pre-populated and the
    CSRF token string. Raises if either piece can't be captured.
    """
    from playwright.sync_api import sync_playwright

    captured = {"token": None}

    def _on_request(req):
        if "fetch/fuel.php" in req.url and req.post_data and not captured["token"]:
            m = re.search(r"token=([0-9a-f]+)", req.post_data)
            if m:
                captured["token"] = m.group(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = ctx.new_page()
        page.on("request", _on_request)
        page.goto(_FUEL_PRICES_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)
        cookies = ctx.cookies()
        browser.close()

    if not captured["token"]:
        raise RuntimeError(
            "tolls.eu: failed to capture CSRF token from /fetch/fuel.php — "
            "endpoint may have changed."
        )

    session = requests.Session()
    for c in cookies:
        session.cookies.set(c["name"], c["value"], domain=c["domain"])
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": _FUEL_PRICES_URL,
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    return session, captured["token"]


def _fetch_country_fuel(
    session: requests.Session, token: str, iso3: str, fuel: str
) -> list[dict]:
    """One POST → list of ``{"x": date, "y": price}`` for a single country & fuel."""
    resp = session.post(
        _ENDPOINT,
        data={"iso3": iso3, "fuel": fuel, "lang": "en", "token": token},
        timeout=20,
    )
    resp.raise_for_status()
    try:
        payload = resp.json()
    except json.JSONDecodeError:
        logger.warning(
            "[tolls_eu] non-JSON response for iso3=%s fuel=%s: %r",
            iso3,
            fuel,
            resp.text[:200],
        )
        return []
    if isinstance(payload, dict) and payload.get("error"):
        logger.info("[tolls_eu] iso3=%s fuel=%s → %s", iso3, fuel, payload["error"])
        return []
    if isinstance(payload, dict) and "values" in payload:
        return payload["values"]
    if isinstance(payload, list):
        return payload
    logger.warning(
        "[tolls_eu] unexpected payload shape for iso3=%s fuel=%s: %r",
        iso3,
        fuel,
        str(payload)[:200],
    )
    return []


def _fetch_country(cc: str, cutoff: date) -> pd.DataFrame | None:
    """Fetch a single microstate's history (all three fuels)."""
    meta = _COUNTRIES[cc]
    session, token = _harvest_session()

    rows: list[dict] = []
    for fuel in _FUELS:
        values = _fetch_country_fuel(session, token, meta["iso3"], fuel)
        product = _PRODUCT_LABELS[fuel]
        for point in values:
            try:
                obs = datetime.strptime(point["x"], "%Y-%m-%d").date()
            except (KeyError, ValueError, TypeError):
                continue
            if obs <= cutoff:
                continue
            raw = point.get("y")
            if raw in (None, "", []):
                continue
            try:
                price = float(raw)
            except (TypeError, ValueError):
                continue
            if not (price > 0):
                continue
            rows.append(
                {
                    "observation_date": obs.isoformat(),
                    "country": meta["name"],
                    "fuel_product": product,
                    "price_local": price,
                    "currency": meta["currency"],
                    "source_key": meta["source_key"],
                    "unit": meta["unit"],
                }
            )

    if not rows:
        return None
    return pd.DataFrame(rows)


def fetch_tolls_mc(cutoff: date) -> pd.DataFrame | None:
    """Monaco fuel prices from tolls.eu (weekly since 2023)."""
    return _fetch_country("mc", cutoff)


def fetch_tolls_li(cutoff: date) -> pd.DataFrame | None:
    """Liechtenstein fuel prices from tolls.eu (weekly since 2023)."""
    return _fetch_country("li", cutoff)


def fetch_tolls_sm(cutoff: date) -> pd.DataFrame | None:
    """San Marino fuel prices from tolls.eu (weekly since 2023)."""
    return _fetch_country("sm", cutoff)
