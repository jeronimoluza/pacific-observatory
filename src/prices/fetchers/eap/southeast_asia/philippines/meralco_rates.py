"""Manila Electric Company (Meralco) — published overall residential electricity rate.

Meralco announces its "overall electricity rate for a typical [residential]
household" (PHP per kWh, all-in: generation + transmission + distribution +
taxes + pass-through charges) in a monthly press release under
company.meralco.com.ph/news-and-advisories/<slug>, where <slug> is either
"lower-rates-<month>-<year>" or "higher-rates-<month>-<year>" depending on
the month's direction. The "rates-archives" listing page is a Drupal Views
listing whose initial HTML only carries the newest item; older items are
revealed by repeatedly clicking a client-side "Show More" button (no
pagination URL/API was found), so this fetcher renders the page with
Playwright and clicks "Show More" a fixed number of times before scraping
every "... Rates this <Month> <Year>" link it can see. Each article page
itself IS server-rendered on a plain GET (no JS needed there), and is
parsed with a regex over the headline sentence, whose exact wording varies
by month ("bringing down the overall rate ... to P<new> from P<old> per
kWh in <PrevMonth>" / "brings down the overall rate ... to P<new> per kWh
this month from P<old> per kWh last <PrevMonth>") — the regex tolerates
both by only anchoring on "to P<new> ... from P<old>".

Only the single headline all-in rate is captured (COICOP 04.5.1.0,
Electricity) — Meralco also publishes a full generation/transmission/
distribution/tax breakdown per class (residential/commercial/industrial),
which would be a separate, more involved fetcher.

Source URL: https://company.meralco.com.ph/news-and-advisories/rates-archives
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

_ARCHIVES_URL = "https://company.meralco.com.ph/news-and-advisories/rates-archives"
_COUNTRY = "Philippines"
_CURRENCY = "PHP"
_SOURCE_KEY = "meralco_rates"
_COICOP_CODE = "04.5.1.0"
_IDENT = ["source_key", "observation_date", "item_name"]
_HEADERS = {"User-Agent": "pacific-observatory/prices (+research)"}

_MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ],
        start=1,
    )
}

_ARTICLE_LINK_RE = re.compile(
    r"<h4>\s*(?:Lower|Higher)\s+Rates\s+this\s+([A-Za-z]+)\s+(\d{4})\s*</h4>"
    r'.*?href="(https://company\.meralco\.com\.ph/news-and-advisories/[a-z0-9-]+)"',
    re.I | re.DOTALL,
)
_RATE_RE = re.compile(
    r"overall (?:electricity )?rate for a typical household to P?\s*([0-9.]+)"
    r"(?:\s+per kWh)?[^.]{0,40}?from P?\s*([0-9.]+)",
    re.I,
)


def _render_archives_html(show_more_clicks: int = 6) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page.goto(_ARCHIVES_URL, timeout=30000, wait_until="networkidle")
        page.wait_for_timeout(3000)
        for _ in range(show_more_clicks):
            try:
                page.get_by_text("Show More", exact=False).first.click(timeout=4000)
                page.wait_for_timeout(2500)
            except Exception:
                break
        html = page.content()
        browser.close()
    return html


def _all_articles() -> list[tuple[date, str]]:
    html = _render_archives_html()
    matches = _ARTICLE_LINK_RE.findall(html)
    candidates = []
    for month_name, year, url in matches:
        month = _MONTHS.get(month_name.lower())
        if not month:
            continue
        candidates.append((date(int(year), month, 1), url))
    candidates.sort(key=lambda x: x[0])
    return candidates


def fetch_meralco_rates(cutoff: date) -> pd.DataFrame | None:
    articles = _all_articles()
    if not articles:
        logger.warning("[%s] could not locate any rates article on %s", _SOURCE_KEY, _ARCHIVES_URL)
        return None

    rows: list[dict] = []
    for obs_date, url in articles:
        if obs_date <= cutoff:
            continue
        resp = requests.get(url, headers=_HEADERS, timeout=30)
        if resp.status_code != 200:
            logger.warning("[%s] HTTP %d for %s", _SOURCE_KEY, resp.status_code, url)
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        m = _RATE_RE.search(text)
        if not m:
            logger.warning("[%s] Could not find rate sentence on %s", _SOURCE_KEY, url)
            continue
        price_local = float(m.group(1))
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": "Meralco overall residential electricity rate (all-in, typical household)",
            "price_local": price_local,
            "currency": _CURRENCY,
            "unit": "kWh",
            "source_url": url,
            "notes": None,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        return None

    df = pd.DataFrame(rows)
    dup_count = int(df["observation_hash"].duplicated().sum())
    if dup_count:
        logger.warning("[%s] %d duplicate observation_hash rows before de-dup", _SOURCE_KEY, dup_count)
        df = df.drop_duplicates(subset="observation_hash")
    return df
