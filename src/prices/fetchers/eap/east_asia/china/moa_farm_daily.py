"""MOA China — national daily wholesale prices (农业农村部 农产品批发市场价格日报).

The Ministry of Agriculture and Rural Affairs publishes a daily national
wholesale-market price bulletin behind the "农产品批发价格200指数" portal at
data.moa.gov.cn. The portal page itself only exposes a two-day rolling window
of nine index values (`/nyb/200zs`), but the bulletin it summarises is served
in full by the ministry's own price system at pfsc.agri.cn:

    POST https://pfsc.agri.cn/api/FarmDaily/list  {"pageNum": N, "pageSize": M}

returns a paginated archive of the daily bulletins -- 1,346 records as of
2026-09-11, i.e. roughly five and a half years of daily history -- each with a
`daylyDate` and a clean plain-text `countentstr` carrying the day's national
average wholesale price for a fixed panel of named commodities in CNY/kg
(元/公斤). No auth, no cookie, no token.

Unlike `cn_xinfadi_wholesale` (Beijing's Xinfadi market only, ~500 SKUs/day,
no meaningful history through the API) this is a *national* average with a
long back-series, over a small closed panel. The two are complements: Xinfadi
gives breadth for one city, this gives a national level for the headline
commodities plus history.

Only the named single-commodity quotes are emitted. The bulletin also carries
two basket averages ("重点监测的28种蔬菜平均价格为4.68元/公斤",
"重点监测的6种水果平均价格") which span many COICOP leaves and map to no single
leaf; they are deliberately dropped rather than given a guessed code.

The index sentences (农产品批发价格200指数 / 菜篮子产品批发价格指数) are index
points, not prices, and belong in an IndexObservation fetcher if they are ever
wanted -- they are not emitted here.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://pfsc.agri.cn/api/FarmDaily/list"
_PORTAL = "https://data.moa.gov.cn/nyb/pc/index.jsp"
_COUNTRY = "China"
_CURRENCY = "CNY"
_SOURCE_KEY = "cn_moa_farm_daily"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]
_PAGE_SIZE = 50
_MAX_PAGES = 40  # 2,000 daily bulletins ceiling; archive held 1,346 on 2026-09-11

# COICOP 2018 leaves for the fixed commodity panel the bulletin quotes.
# Codes taken from data/prices/enrich/coicop_categories.xlsx and cross-checked
# against the audited map in xinfadi_wholesale.py (鲫鱼/鲤鱼/鲢鱼 -> 01.1.3.1.1,
# 带鱼 -> 01.1.3.1.9, 白条猪 -> 01.1.2.2.2, 柴鸡蛋 -> 01.1.4.8.1), so the two
# China wholesale sources land the same commodity on the same leaf.
#
# 大带鱼 (largehead hairtail) is marine but follows xinfadi's 带鱼 -> 01.1.3.1.9
# ("Other fish, live, fresh, chilled or frozen") rather than being forced into
# one of the named pelagic leaves.
_COICOP_MAP: dict[str, str] = {
    "猪肉": "01.1.2.2.2",  # pork, fresh
    "牛肉": "01.1.2.2.1",  # beef
    "羊肉": "01.1.2.2.3",  # mutton / goat
    "白条鸡": "01.1.2.2.4",  # dressed chicken
    "鸡蛋": "01.1.4.8.1",  # hen eggs in shell
    "鲫鱼": "01.1.3.1.1",  # crucian carp (freshwater)
    "鲤鱼": "01.1.3.1.1",  # common carp (freshwater)
    "白鲢鱼": "01.1.3.1.1",  # silver carp (freshwater)
    "花鲢鱼": "01.1.3.1.1",  # bighead carp (freshwater) -- pre-2022 panel only
    "草鱼": "01.1.3.1.1",  # grass carp (freshwater) -- pre-2022 panel only
    "大带鱼": "01.1.3.1.9",  # largehead hairtail
    "大黄花鱼": "01.1.3.1.9",  # large yellow croaker -- pre-2022 panel only
}

# The bulletin renamed its aquatic panel around 2022: the pre-2022 text says
# 活草鱼 / 活鲫鱼 / 活鲤鱼 / 花鲢活鱼 / 白鲢活鱼 ("live <fish>") where the
# current text says 鲫鱼 / 鲤鱼 / 白鲢鱼. Both spellings are matched and folded
# onto one canonical item_name so a single fish does not split into two series
# at the rename. Keys here are what appears in the bulletin; values are the
# canonical name used downstream and looked up in _COICOP_MAP above.
_ALIASES: dict[str, str] = {name: name for name in _COICOP_MAP}
_ALIASES.update(
    {
        "活鲫鱼": "鲫鱼",
        "活鲤鱼": "鲤鱼",
        "白鲢活鱼": "白鲢鱼",
        "花鲢活鱼": "花鲢鱼",
        "活草鱼": "草鱼",
    }
)

# "猪肉平均价格为16.20元/公斤" and "牛肉70.26元/公斤" are both in the same
# sentence run; the optional 平均价格为 covers the first form.
#
# The commodity name is an explicit alternation over the _ALIASES keys, NOT a
# generic Han-character class. A generic class is the obvious way to write this
# and it is wrong: `[一-鿿]{2,6}?` in
# "...全国农产品批发市场猪肉平均价格为16.20元/公斤" matches leftmost-first at
# "批发市场猪肉", which is not a map key -- and finditer then resumes past it,
# so the pork price is silently lost. Longest-first ordering keeps 白鲢活鱼
# from being truncated to a shorter alternative.
#
# A missing value is rendered as a literal "-" ("猪肉平均价格为-元/公斤"), which
# \d+ cannot match, so outage days drop out instead of banking a zero.
_PRICE_RE = re.compile(
    r"(?P<name>"
    + "|".join(sorted((re.escape(k) for k in _ALIASES), key=len, reverse=True))
    + r")(?:平均价格为)?(?P<price>\d+(?:\.\d+)?)元/公斤"
)


def _bulletin_text(rec: dict) -> str:
    """Prefer the clean plain-text field; fall back to the per-family fields."""
    txt = str(rec.get("countentstr") or "").strip()
    if txt:
        return txt
    parts = [
        str(rec.get(k) or "")
        for k in ("animalConclusion", "aquaticConclusion")
    ]
    return "".join(parts)


def _parse_bulletin(rec: dict) -> list[tuple[str, float]]:
    """Return [(item_name, price_cny_per_kg)] for the mapped commodity panel."""
    out: list[tuple[str, float]] = []
    seen: set[str] = set()
    for m in _PRICE_RE.finditer(_bulletin_text(rec)):
        name = _ALIASES.get(m.group("name"), m.group("name"))
        if name in seen:
            continue
        try:
            price = float(m.group("price"))
        except ValueError:
            continue
        if not 0 < price < 10_000:
            continue
        seen.add(name)
        out.append((name, price))
    return out


def _fetch_page(session, page: int) -> list[dict] | None:
    try:
        resp = session.post(
            _URL,
            json={"pageNum": page, "pageSize": _PAGE_SIZE},
            headers={
                "Origin": "https://pfsc.agri.cn",
                "Referer": "https://pfsc.agri.cn/",
                "Content-Type": "application/json",
            },
            timeout=60,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] page %d fetch failed: %s", _SOURCE_KEY, page, exc)
        return None
    if payload.get("code") != 200:
        logger.warning("[%s] page %d: %s", _SOURCE_KEY, page, payload.get("message"))
        return None
    return (payload.get("content") or {}).get("list") or []


def fetch_cn_moa_farm_daily(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    ts = get_scrape_ts()
    rows: list[dict] = []
    seen: set[str] = set()
    unmapped: set[str] = set()
    page = 1
    stop = False

    while page <= _MAX_PAGES and not stop:
        batch = _fetch_page(session, page)
        if batch is None:
            break
        if not batch:
            break
        for rec in batch:
            raw_date = str(rec.get("daylyDate") or "").strip()
            try:
                obs_date = pd.to_datetime(raw_date).date()
            except (ValueError, TypeError):
                continue
            # The archive is served newest-first, so the first bulletin at or
            # before the cutoff means every later page is also old.
            if obs_date <= cutoff:
                stop = True
                continue
            quotes = _parse_bulletin(rec)
            if not quotes:
                logger.warning(
                    "[%s] %s: no priced commodity parsed from bulletin",
                    _SOURCE_KEY,
                    obs_date,
                )
                continue
            for name, price in quotes:
                code = _COICOP_MAP.get(name)
                if not code:
                    unmapped.add(name)
                    continue
                row = {
                    "observation_date": obs_date.isoformat(),
                    "period_kind": "daily",
                    "country": _COUNTRY,
                    "source_key": _SOURCE_KEY,
                    "item_name": name,
                    "coicop_code": code,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": "kg",
                    "source_url": _PORTAL,
                    "notes": (
                        "national average wholesale price, MOA daily bulletin "
                        "(农产品批发市场价格日报)"
                    ),
                    "scrape_ts": ts,
                    "observation_hash": None,
                }
                row["observation_hash"] = make_hash(row, _IDENT)
                if row["observation_hash"] in seen:
                    continue
                seen.add(row["observation_hash"])
                rows.append(row)
        if len(batch) < _PAGE_SIZE:
            break
        page += 1
        time.sleep(0.3)

    if page > _MAX_PAGES:
        logger.warning(
            "[%s] stopped at MAX_PAGES=%d — older bulletins were NOT collected",
            _SOURCE_KEY,
            _MAX_PAGES,
        )
    if unmapped:
        logger.info("[%s] unmapped commodity names skipped: %s", _SOURCE_KEY, sorted(unmapped))
    logger.info("[%s] %d rows (cutoff=%s, pages=%d)", _SOURCE_KEY, len(rows), cutoff, page)
    return pd.DataFrame(rows) if rows else None
