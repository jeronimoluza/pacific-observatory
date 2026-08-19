"""CNMI Dept of Commerce, Central Statistics Division (CSD) — Consumer Price Index, Saipan.

Published quarterly at
ver1.cnmicommerce.com/divisions/central-statistics/report-hub/cnmi-consumer-price-index-saipan/
as a WordPress page with the full historical series embedded directly in three
TablePress HTML tables (quarter-over-quarter % change, year-over-year % change,
and the index level itself, back to 2003 Q1) -- no PDF/XLSX download required.

The live site 403s with a "cannot access this website due to your location"
branded error page from non-CNMI/US IPs (Cloudflare-fronted country-wide IP
allowlist, not a structural anti-bot -- see known_blockers.md "Country-wide
IP-fence cohort"). Direct fetch is attempted first (may work from the
production run's own IP); the Wayback Machine mirror -- captured as recently
as 2025-11-10 -- is the fallback and what this fetcher was verified against.

The three TablePress tables share identical column headers; the index-level
table is distinguished from the two %-change tables by magnitude (its "All
Items" column never dips below ~30, vs. the %-change tables which hover near
zero including negatives).

CNMI CSD's own grouping is a flatter, US-BLS-style 10-column scheme, not the
standard COICOP-2018 13-division grouping. Mapped to the closest COICOP-2018
division per label below; "Education & Communication" is a genuinely combined
column (no single division covers both) and is dropped rather than forced
into a misleading code, matching the SINSO Solomon Islands and Tuvalu CPI
fetchers' handling of their own ambiguous combined labels. "All Items" is the
headline row, dropped pending a sanctioned sentinel code (see the onboarding
skill's open design questions).

Emits IndexObservation rows (analytical_role: cpi_benchmark).
coicop_classification: publisher_labeled (static _COICOP_MAP below).
"""

from __future__ import annotations

import html as html_lib
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Northern Mariana Islands"
_SOURCE_KEY = "mp_cnmi_cpi"
_IDENT = ["source_key", "observation_date", "coicop_code"]
_BASE_PERIOD = "2007=100"
_LIVE_URL = (
    "https://ver1.cnmicommerce.com/divisions/central-statistics/"
    "report-hub/cnmi-consumer-price-index-saipan/"
)
_CDX_URL = (
    "https://web.archive.org/cdx/search/cdx"
    "?url=ver1.cnmicommerce.com/divisions/central-statistics/report-hub/"
    "cnmi-consumer-price-index-saipan/&output=json&filter=statuscode:200&limit=-1"
)

_COICOP_MAP = {
    "Food": "01",
    "Alcoholic Beverages": "02",
    "Housing & Utilities": "04",
    "Apparel": "03",
    "Transportation": "07",
    "Medical Care": "06",
    "Recreation": "09",
    "Other Goods & Services": "12",
}
_DROP_LABELS = {"All Items", "Education & Communication"}

_QUARTER_MONTH = {"1st Qtr": 1, "2nd Qtr": 4, "3rd Qtr": 7, "4th Qtr": 10}

_TABLEPRESS_RE = re.compile(
    r'<table[^>]*class="[^"]*tablepress[^"]*"[^>]*>.*?</table>', re.S
)


def _latest_wayback_url(session) -> str | None:
    try:
        resp = session.get(_CDX_URL, timeout=30)
        resp.raise_for_status()
        rows = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] Wayback CDX lookup failed: %s", _SOURCE_KEY, exc)
        return None
    if len(rows) < 2:
        return None
    timestamp = rows[-1][1]
    return f"https://web.archive.org/web/{timestamp}/{_LIVE_URL}"


def _fetch_html(session) -> tuple[str, str] | None:
    try:
        resp = session.get(_LIVE_URL, timeout=30)
        if resp.status_code == 200:
            return resp.text, _LIVE_URL
        logger.info(
            "[%s] direct fetch HTTP %d, falling back to Wayback",
            _SOURCE_KEY,
            resp.status_code,
        )
    except Exception as exc:  # noqa: BLE001
        logger.info(
            "[%s] direct fetch failed (%s), falling back to Wayback", _SOURCE_KEY, exc
        )

    wb_url = _latest_wayback_url(session)
    if not wb_url:
        return None
    try:
        resp = session.get(wb_url, timeout=60)
        resp.raise_for_status()
        return resp.text, wb_url
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] Wayback fetch failed: %s", _SOURCE_KEY, exc)
        return None


def _parse_index_table(html: str) -> list[tuple[int, str, dict[str, float]]]:
    """Return [(year, quarter_label, {column_label: value}), ...] from the
    index-level TablePress table (picked by magnitude, see module docstring)."""
    tables = _TABLEPRESS_RE.findall(html)
    candidates = []
    for t in tables:
        head_m = re.search(r"<thead>.*?</thead>", t, re.S)
        if not head_m:
            continue
        headers = [
            html_lib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h))).strip()
            for h in re.findall(r"<th[^>]*>(.*?)</th>", head_m.group())
        ]
        if (
            "Year" not in headers
            or "Quarter" not in headers
            or "All Items" not in headers
        ):
            continue
        body_m = re.search(r"<tbody.*?</tbody>", t, re.S)
        if not body_m:
            continue
        trs = re.findall(r"<tr[^>]*>(.*?)</tr>", body_m.group(), re.S)
        rows = []
        all_items_vals = []
        for tr in trs:
            cells = [
                html_lib.unescape(
                    re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c))
                ).strip()
                for c in re.findall(r"<td[^>]*>(.*?)</td>", tr)
            ]
            if len(cells) != len(headers):
                continue
            rows.append(dict(zip(headers, cells)))
            try:
                all_items_vals.append(float(cells[headers.index("All Items")]))
            except (ValueError, IndexError):
                pass
        if all_items_vals and min(all_items_vals) > 30:
            candidates.append(rows)

    if not candidates:
        return []
    # Prefer the (only) candidate; if magnitude heuristic somehow returns more
    # than one, take the longest (fullest history).
    best = max(candidates, key=len)

    out = []
    for row in best:
        try:
            year = int(row["Year"])
        except (KeyError, ValueError):
            continue
        quarter_label = row.get("Quarter", "")
        values = {}
        for label in list(_COICOP_MAP) + list(_DROP_LABELS):
            raw = row.get(label)
            if raw in (None, ""):
                continue
            try:
                values[label] = float(raw)
            except ValueError:
                continue
        out.append((year, quarter_label, values))
    return out


def fetch_mp_cnmi_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120 Safari/537.36"
        }
    )

    fetched = _fetch_html(session)
    if not fetched:
        logger.warning("[%s] could not fetch CPI page (direct or Wayback)", _SOURCE_KEY)
        return None
    html, source_url = fetched

    parsed = _parse_index_table(html)
    if not parsed:
        logger.warning("[%s] no index-level table found on page", _SOURCE_KEY)
        return None

    ts_scrape = get_scrape_ts()
    rows: list[dict] = []
    for year, quarter_label, values in parsed:
        month = _QUARTER_MONTH.get(quarter_label)
        if month is None:
            continue
        obs_date = date(year, month, 1)
        if obs_date <= cutoff:
            continue
        for label, index_value in values.items():
            if label in _DROP_LABELS:
                if label == "Education & Communication":
                    logger.debug(
                        "[%s] dropping combined 'Education & Communication' column "
                        "(no single COICOP division)",
                        _SOURCE_KEY,
                    )
                continue
            coicop = _COICOP_MAP.get(label)
            if coicop is None:
                logger.warning(
                    "[%s] no COICOP mapping for %r — dropping row", _SOURCE_KEY, label
                )
                continue
            r = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "quarterly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "index_value": round(index_value, 4),
                "index_base_period": _BASE_PERIOD,
                "source_url": source_url,
                "notes": f"category={label}",
                "scrape_ts": ts_scrape,
                "observation_hash": None,
            }
            r["observation_hash"] = make_hash(r, _IDENT)
            rows.append(r)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
