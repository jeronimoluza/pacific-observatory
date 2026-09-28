"""EriTel Eritrea -- telecom tariff schedules (mobile GSM, fixed PSTN, VDSL/
ADSL/Wifi/VSAT internet).

eritel.com.er (Eritrea's sole telecom operator, state-owned) publishes its
full retail tariff schedule as plain server-rendered HTML tables across
three service pages (Mobile GSM, Fixed Telephony, Internet Services). No
JS rendering required; no WAF (plain `requests` clears it, confirmed 2026-
09-28).

Emits PriceObservation rows (analytical_role: tariff, coicop_classification:
source_curated -> "08.3.0" telephone/telefax/internet access services).

Only tables whose immediately preceding heading contains "Schedule of
Charges" are parsed -- this cleanly selects the priced tariff tables and
skips the non-priced "Eritel Service Areas" list, the inter-service-area
tariff-category matrix, and the vertical package spec sheets (e.g. "ADSL
Silver 1GB Package", which lists Bandwidth/Volume/Price as ROWS describing
one plan rather than one row per priced item). One-time deployment/
installation charge tables are left for a follow-up pass -- their headings
say "Deployment Charges", not "Schedule of Charges".

CURRENCY: everything is Nakfa (NKF on-page, ISO code ERN) except the VSAT
table, whose own column header says "Monthly Fee*in USD" -- emitted as USD,
not converted, per that table's own labelling.

Onboarded per the w40 brief (Eritrea: 0 sources, honest true zero otherwise
-- see references/inventories/ssa/eritrea.md for the confirmed structural
absence of domestic online retail). This is the country's only verified
institutional/tariff source.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
import requests
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_PAGES = {
    "https://eritel.com.er/contents.php?id=1017": "Mobile GSM Services",
    "https://eritel.com.er/contents.php?id=1018": "Fixed Telephony Services",
    "https://eritel.com.er/contents.php?id=1020": "Internet Services",
}
_COUNTRY = "Eritrea"
_SOURCE_KEY = "er_eritel_tariffs"
_DEFAULT_CURRENCY = "ERN"
_COICOP = "08.3.0"
_IDENT = ["source_key", "item_name", "unit"]


def _parse_num(text: str) -> float | None:
    cleaned = text.replace(",", "")
    m = re.search(r"\d*\.?\d+", cleaned)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _section_heading(table) -> str | None:
    for prev in table.find_all_previous(["h2", "h3", "h4"]):
        txt = prev.get_text(strip=True)
        if txt:
            return txt
    return None


def _parse_tables(html: str, page_label: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows_out: list[dict] = []
    for table in soup.select("table.table-bordered"):
        heading = _section_heading(table)
        if not heading or "schedule of charges" not in heading.lower():
            continue
        section = heading.split(":")[0].strip() or heading
        trs = table.find_all("tr")
        if len(trs) < 2:
            continue
        header_cells = [c.get_text(strip=True) for c in trs[0].find_all(["td", "th"])]
        ncols = len(header_cells)
        currency = (
            "USD" if any("usd" in h.lower() for h in header_cells) else _DEFAULT_CURRENCY
        )

        for tr in trs[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) != ncols or not cells[0]:
                continue

            if ncols == 2:
                price = _parse_num(cells[1])
                if price is None:
                    continue
                unit = "unspecified"
                low = cells[1].lower()
                if "per minute" in low:
                    unit = "minute"
                elif "per sms" in low:
                    unit = "sms"
                elif "month" in low:
                    unit = "month"
                rows_out.append(
                    {
                        "item_name": f"EriTel {section} — {cells[0]}",
                        "price_local": price,
                        "currency": currency,
                        "unit": unit,
                        "source_url_label": page_label,
                    }
                )
            elif ncols == 3 and "peak" in (header_cells[1] + header_cells[2]).lower():
                for label, val in ((header_cells[1], cells[1]), (header_cells[2], cells[2])):
                    price = _parse_num(val)
                    if price is None:
                        continue
                    rows_out.append(
                        {
                            "item_name": f"EriTel {section} — {cells[0]} ({label})",
                            "price_local": price,
                            "currency": currency,
                            "unit": "minute",
                            "source_url_label": page_label,
                        }
                    )
            elif ncols == 5:
                price = _parse_num(cells[4])
                if price is None:
                    continue
                rows_out.append(
                    {
                        "item_name": (
                            f"EriTel {section} — {cells[0]} kbps "
                            f"(DL {cells[1]}/UL {cells[2]} kbps)"
                        ),
                        "price_local": price,
                        "currency": currency,
                        "unit": "month",
                        "source_url_label": page_label,
                    }
                )
            elif ncols == 4 and "usd" in header_cells[-1].lower():
                price = _parse_num(cells[-1])
                if price is None:
                    continue
                rows_out.append(
                    {
                        "item_name": f"EriTel {section} — {cells[1]}",
                        "price_local": price,
                        "currency": "USD",
                        "unit": "month",
                        "source_url_label": page_label,
                    }
                )
    return rows_out


def fetch_er_eritel_tariffs(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        return None

    session = requests.Session()
    session.headers.update({"User-Agent": _UA})

    parsed: list[dict] = []
    for url, page_label in _PAGES.items():
        try:
            resp = session.get(url, timeout=30)
        except requests.RequestException as exc:
            logger.warning("[%s] Request failed for %s: %s", _SOURCE_KEY, url, exc)
            continue
        if resp.status_code != 200:
            logger.warning("[%s] HTTP %s for %s", _SOURCE_KEY, resp.status_code, url)
            continue
        page_rows = _parse_tables(resp.text, page_label)
        for r in page_rows:
            r["source_url"] = url
        parsed.extend(page_rows)

    if not parsed:
        logger.warning("[%s] No tariff rows parsed", _SOURCE_KEY)
        return None

    # De-dupe: the International Call Tariffs table is published identically
    # on both the Mobile GSM (1017) and Fixed Telephony (1018) pages.
    seen = set()
    rows: list[dict] = []
    for p in parsed:
        key = (p["item_name"], p["price_local"], p["currency"])
        if key in seen:
            continue
        seen.add(key)
        row = {
            "observation_date": today.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": p["item_name"],
            "price_local": p["price_local"],
            "currency": p["currency"],
            "unit": p["unit"],
            "coicop_code": _COICOP,
            "source_url": p["source_url"],
            "notes": p["source_url_label"],
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
