"""ERA (Electricity Regulatory Authority, Uganda) -- quarterly End-User
Electricity Tariffs for UEDCL customers.

ERA publishes a quarterly press-release post at era.go.ug (WordPress)
announcing the approved End-user Electricity Tariff for the upcoming
quarter, per consumer category (Domestic, Commercial, Medium/Large/
Extra-Large Industrial, ...(Service) variants, Public Amenities), plus a
Lifeline tariff for low-consumption domestic customers and a Cooking
tariff bundle. There is no separate tariff-schedule table page or
download -- the numbers are stated as plain sentences in the post body,
so this fetcher discovers the latest post and regex-parses the numbers
out of the rendered text rather than a table.

1. GET /wp-json/wp/v2/posts?search=electricity+tariffs+for+the&per_page=10
   &orderby=date&order=desc (WordPress REST API, no auth). Filter titles
   containing "Tariff" AND one of {"Quarter", "Approves", "Retains",
   "Reduces", "Sets"} (rules out unrelated stakeholder-engagement posts
   that also match "electricity tariff" in free text), then pick the
   newest by post date.
2. Strip HTML from `content.rendered`, collapse whitespace, and regex out
   the sentence "As per the approved Tariff schedule, <category> UGX
   <price>; <category> UGX <price>; ... and the <category> UGX <price>
   per unit." -- 9 categories in the 2026-08-31 sample (Domestic,
   Commercial, Medium Industrial, Medium (Service), Large Industrial,
   Large (Service), Extra-Large Industrial, Extra-Large (Service), Public
   Amenities). Each category becomes one PriceObservation row, unit=kWh.
3. Two more single-value tariffs are parsed opportunistically (present in
   the 2026-08-31 sample, but the fetcher does not fail if a future post
   drops the exact phrasing): the Lifeline tariff for domestic customers
   under a monthly-average-consumption threshold, and the Cooking tariff
   bundle rate.

observation_date = the post's WordPress publish date (period_kind=
"quarterly", matching the source's actual cadence) -- ERA's posts do not
always state an explicit "effective from" date distinct from the
announcement date.

COICOP: 04.5.1 (electricity), matching ura_electricity_tariff.py (Vanuatu)
and cie_tariff.py (Cote d'Ivoire) convention in this repo.

TLS: era.go.ug required no `verify=False` workaround in testing (chain
validated fine); left as a plain `get_session()` call. If a future run
hits an SSLError here, add verify=False per the documented pattern used
elsewhere in this repo (ubos_cpi.py, vnso_cpi.py, cie_tariff.py).
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_WP_API = "https://www.era.go.ug/wp-json/wp/v2/posts"
_COUNTRY = "Uganda"
_CURRENCY = "UGX"
_SOURCE_KEY = "uga_era_tariff"
_COICOP_CODE = "04.5.1"
_IDENT = ["source_key", "observation_date", "item_name"]

_TITLE_KEYWORDS = ("quarter", "approves", "retains", "reduces", "sets", "announces")

_MAIN_BLOCK_RE = re.compile(
    r"approved Tariff schedule,\s*(.+?)\s+per unit\.", re.IGNORECASE
)
_CATEGORY_RE = re.compile(r"^(.+?)\s+UGX\s+([\d,]+\.?\d*)$")

_LIFELINE_RE = re.compile(
    r"Lifeline Tariff for Domestic Customers.*?at UGX\s+([\d,]+\.?\d*)\s+for the First (\d+) Units?",
    re.IGNORECASE | re.DOTALL,
)
_COOKING_RE = re.compile(
    r"Cooking Tariff.*?at UGX\s+([\d,]+\.?\d*)\s+per unit for a (\d+)-unit bundle",
    re.IGNORECASE | re.DOTALL,
)


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^<]+?>", " ", html)
    text = text.replace("&#8217;", "'").replace("&#8211;", "-").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def _parse_ugx(text: str) -> float | None:
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _find_latest_post(posts: list[dict]) -> dict | None:
    best: dict | None = None
    for p in posts:
        title = _strip_html(p.get("title", {}).get("rendered", "")).lower()
        if "tariff" not in title:
            continue
        if not any(kw in title for kw in _TITLE_KEYWORDS):
            continue
        pub_date = p.get("date")
        if not pub_date:
            continue
        if best is None or pub_date > best["date"]:
            best = p
    return best


def _extract_rows(text: str, obs_date: date) -> list[dict]:
    rows: list[dict] = []
    ts = get_scrape_ts()

    m = _MAIN_BLOCK_RE.search(text)
    if m:
        block = m.group(1)
        parts = re.split(r";\s*|\s+and the\s+", block)
        for part in parts:
            part = part.replace("will pay an average of", "").strip()
            cm = _CATEGORY_RE.match(part)
            if not cm:
                continue
            category = re.sub(r"\s+", " ", cm.group(1)).strip()
            price = _parse_ugx(cm.group(2))
            if price is None:
                continue
            rows.append(
                {
                    "item_name": f"ERA UEDCL End-User Tariff, {category}",
                    "price_local": price,
                    "unit": "kWh",
                }
            )
    else:
        logger.warning(
            "[%s] Main tariff-schedule sentence not found in post", _SOURCE_KEY
        )

    lm = _LIFELINE_RE.search(text)
    if lm:
        rows.append(
            {
                "item_name": (
                    f"ERA UEDCL End-User Tariff, Lifeline (Domestic, first "
                    f"{lm.group(2)} units)"
                ),
                "price_local": _parse_ugx(lm.group(1)),
                "unit": "kWh",
            }
        )

    cm = _COOKING_RE.search(text)
    if cm:
        rows.append(
            {
                "item_name": f"ERA UEDCL End-User Tariff, Cooking ({cm.group(2)}-unit bundle)",
                "price_local": _parse_ugx(cm.group(1)),
                "unit": "kWh",
            }
        )

    out = []
    for r in rows:
        if r["price_local"] is None:
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "quarterly_start",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": r["item_name"],
            "price_local": r["price_local"],
            "currency": _CURRENCY,
            "unit": r["unit"],
            "source_url": None,
            "notes": "ERA quarterly End-User Electricity Tariff press release, UEDCL customers",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        out.append(row)
    return out


def fetch_uga_era_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    resp = session.get(
        _WP_API,
        params={
            "search": "electricity tariffs for the",
            "per_page": 10,
            "orderby": "date",
            "order": "desc",
        },
        timeout=30,
    )
    resp.raise_for_status()
    posts = resp.json()
    post = _find_latest_post(posts)
    if post is None:
        logger.warning("[%s] No qualifying ERA tariff post found", _SOURCE_KEY)
        return None

    post_url = post["link"]
    obs_date = datetime.fromisoformat(post["date"]).date()
    if obs_date <= cutoff:
        return None

    text = _strip_html(post.get("content", {}).get("rendered", ""))
    rows = _extract_rows(text, obs_date)
    if not rows:
        logger.warning("[%s] Parsed zero tariff rows from %s", _SOURCE_KEY, post_url)
        return None
    for row in rows:
        row["source_url"] = post_url

    return pd.DataFrame(rows)
