"""MTN Rwanda — prepaid data and voice/data-combo bundle tariffs.

Scrapes the SSR HTML bundle-listing pages at mtn.co.rw. The site is a
WordPress + Elementor build; each bundle is rendered as an Elementor
"loop-item" (``data-elementor-type="loop-item"``) whose CSS class carries the
validity period as ``bundle-type-<daily|weekly|monthly>``, and whose content
holds a "DATA" heading (data allowance), an optional "MIN" heading (voice
minutes, combo bundles only), and a price button
(``span.elementor-button-text``, e.g. "Rwf 7000"). No JS execution is
required — the tariff table is present in the raw server response.

Two pages are folded into one fetcher:
  - Data-only prepaid bundles (COICOP 08.1.0 — telephone and internet
    access services)
  - Combo data+voice prepaid bundles (same COICOP; still telecom access)

RWF is an integer currency — prices on this site are always whole francs
(e.g. "Rwf 7000"), so no decimal precision is fabricated; the comma
thousands separator (when present) is stripped before ``float()``.

Source URLs: https://www.mtn.co.rw/bundle-category/data-bundles/
             https://www.mtn.co.rw/bundle-category/voice/
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_DATA_URL = "https://www.mtn.co.rw/bundle-category/data-bundles/"
_VOICE_URL = "https://www.mtn.co.rw/bundle-category/voice/"
_COUNTRY = "Rwanda"
_CURRENCY = "RWF"
_SOURCE_KEY = "mtn_rw_bundles"
_COICOP_CODE = "08.1.0"
_IDENT = ["source_key", "observation_date", "item_name"]

_PRICE_RE = re.compile(r"([\d,]+)")


def _heading_texts(item) -> list[str]:
    headings = item.find_all(
        ["h1", "h2", "h3", "p"], class_=re.compile("elementor-heading-title")
    )
    return [h.get_text(strip=True) for h in headings]


def _extract_bundles(
    soup: BeautifulSoup, obs_date: date, source_url: str, label: str
) -> list[dict]:
    rows: list[dict] = []
    items = soup.find_all("div", attrs={"data-elementor-type": "loop-item"})
    for item in items:
        classes = item.get("class", [])
        validity = next(
            (
                c.replace("bundle-type-", "")
                for c in classes
                if c.startswith("bundle-type-")
            ),
            "unknown",
        )
        texts = _heading_texts(item)
        data_amount = None
        voice_minutes = None
        for i, t in enumerate(texts):
            if t == "DATA" and i + 1 < len(texts):
                data_amount = texts[i + 1]
            if t == "MIN" and i + 1 < len(texts):
                voice_minutes = texts[i + 1]

        price_btn = item.find("span", class_="elementor-button-text")
        if not price_btn or not data_amount:
            continue
        price_text = price_btn.get_text(strip=True)
        m = _PRICE_RE.search(price_text)
        if not m:
            continue
        price_local = float(m.group(1).replace(",", ""))

        if voice_minutes:
            item_name = (
                f"MTN Rwanda prepaid bundle, {data_amount} data + {voice_minutes} voice, "
                f"{validity}"
            )
        else:
            item_name = f"MTN Rwanda prepaid data bundle, {data_amount}, {validity}"

        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": item_name,
            "price_local": price_local,
            "currency": _CURRENCY,
            "unit": "bundle",
            "source_url": source_url,
            "notes": f"{label}, validity={validity}",
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def fetch_mtn_rw_bundles(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    obs_date = date.today()
    if obs_date <= cutoff:
        return None

    rows: list[dict] = []

    for url, label in [
        (_DATA_URL, "data bundle"),
        (_VOICE_URL, "voice+data combo bundle"),
    ]:
        resp = session.get(url, timeout=30)
        if resp.status_code != 200:
            logger.warning("[%s] HTTP %d for %s", _SOURCE_KEY, resp.status_code, url)
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        batch = _extract_bundles(soup, obs_date, url, label)
        if not batch:
            logger.warning("[%s] No bundles parsed from %s", _SOURCE_KEY, url)
        rows.extend(batch)

    if not rows:
        return None

    df = pd.DataFrame(rows)
    dup_count = int(df["observation_hash"].duplicated().sum())
    if dup_count:
        logger.warning(
            "[%s] %d duplicate observation_hash rows before de-dup",
            _SOURCE_KEY,
            dup_count,
        )
        df = df.drop_duplicates(subset="observation_hash")
    return df
