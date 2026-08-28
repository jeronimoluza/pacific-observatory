"""Korea Consumer Agency 참가격 (price.go.kr) — daily necessities item price info.

`getPriceItemInfoList.do` is a classic JSP form-POST grid, not a JSON AJAX
endpoint: the "조회" button does `$("#schForm").submit()`, and the server
re-renders the full page with the results embedded as HTML. There is no
`/ajax/`-shaped endpoint for the price grid itself (the filter dropdowns
*are* small JSON endpoints — `getItemGroupCodeList.do`, `getGoodCodeList.do`,
`getInspectYear/Month/Day.do` — used here to discover the item taxonomy and
the latest inspection date).

Taxonomy is 3-level: 13 item groups (`HIGH_CODE`) -> 168 small classes
(`goodSmlclsCode`) -> ~450 named branded products (`goodId`). Each product's
result page embeds a "전국 전체 판매점 평균" (nationwide all-outlet average)
summary block as `<input type="hidden" id="hid_avgPrice_{goodId}" value=...>`
— that is the one row this fetcher emits per product per inspection date, not
the per-outlet rows (which would be tens of thousands of rows and duplicate
the same average many times over).

Quirks confirmed by direct probing (see /tmp/kr_pricego_probe/ for raw
samples):
  - `goodClassCode` in the POST body must be the group-level `HIGH_CODE`, not
    the small-class code itself (`goodSmlclsCode`). Sending the small-class
    code there silently returns zero results ("검색된 내용이 없습니다").
  - `goodId` must be set to a specific product id to get that product's own
    average — leaving it blank returns only one arbitrary product's summary
    even when the small class has several.
  - The endpoint is stateless: no session cookie / CSRF token needed. A bare
    POST with no prior GET returns the same result as a full browser session.
  - Inspection dates are biweekly (survey Wed for dept-store/convenience,
    Thu for hypermarket/supermarket) and go back to 2020 per
    `getInspectYear.do` — real historical depth, not just a current snapshot.
  - The server only sends its leaf TLS certificate (no intermediate), which
    trips Python's ssl module (curl's system trust store papers over it via
    AIA chasing) — hence `verify=False`, same as `vnso_cpi.py` / `acodeco_cbfa.py`.

Basket spans many COICOP divisions (food, personal care 이미용품, household
cleaning/kitchen 세탁·주방·가사용품), so COICOP tagging is left to the
downstream classifier rather than a hand-written map.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import pandas as pd
import requests
import urllib3

from prices.fetchers.utils import get_scrape_ts, make_hash

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

_BASE = "https://www.price.go.kr/tprice/portal/dailynecessitypriceinfo/priceiteminfo"
_COMMON = "https://www.price.go.kr/tprice/common/code"
_LIST_URL = f"{_BASE}/getPriceItemInfoList.do"

_COUNTRY = "Korea, Rep."
_CURRENCY = "KRW"
_SOURCE_KEY = "kr_price_go"
_ENTP_TYPES = ["LM", "DP", "SM", "TR", "CS"]  # 대형마트/백화점/슈퍼마켓/전통시장/편의점
_IDENT = ["source_key", "observation_date", "item_name"]

_TIMEOUT = 20
_MAX_WORKERS = 8

_AVG_PRICE_RE = re.compile(r'id="hid_avgPrice_(\d+)"\s+value="(\d+)"')
_H3_RE = re.compile(r"<h3>([^<]*)</h3>")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }
    )
    s.verify = False
    return s


def _post_json(session: requests.Session, url: str, data: dict) -> list[dict]:
    resp = session.post(url, data=data, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("json", [])


def _latest_inspect_date(session: requests.Session) -> date | None:
    years = _post_json(session, f"{_BASE}/getInspectYear.do", {})
    if not years:
        return None
    year = years[0]["CODE"]
    months = _post_json(session, f"{_BASE}/getInspectMonth.do", {"inspectYear": year})
    if not months:
        return None
    month = months[0]["CODE"]
    days = _post_json(
        session,
        f"{_BASE}/getInspectDay.do",
        {"inspectYear": year, "inspectMonth": month},
    )
    if not days:
        return None
    day = days[0]["CODE"]
    return date(int(year), int(month), int(day))


def _small_classes(session: requests.Session) -> list[dict]:
    """All (goodSmlclsCode, HIGH_CODE/group code, name) triples in one call."""
    return _post_json(session, f"{_COMMON}/getItemGroupCodeList.do", {"itemLevel": 3})


def _good_ids(session: requests.Session, sml_code: str) -> list[dict]:
    return _post_json(
        session, f"{_BASE}/getGoodCodeList.do", {"goodSmlclsCode": sml_code}
    )


def _fetch_one_avg(
    session: requests.Session,
    sml_code: str,
    group_code: str,
    good_id: str,
    inspect_date: date,
) -> tuple[str, int] | None:
    payload = {
        "inspectYear": f"{inspect_date.year:04d}",
        "inspectMonth": f"{inspect_date.month:02d}",
        "inspectDay": f"{inspect_date.day:02d}",
        "chk_entpType": _ENTP_TYPES,
        "entpAreaCode": "",
        "entpId": "",
        "goodSmlclsCode": sml_code,
        "goodId": good_id,
        "pageUnit": "1",
        "searchType": "btnSearch",
        "entpTypeTab": "ALL",
        "entpTypeArr": ",".join(_ENTP_TYPES),
        "goodClassCode": group_code,
    }
    try:
        resp = session.post(_LIST_URL, data=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[%s] price fetch failed for goodId=%s: %s", _SOURCE_KEY, good_id, exc
        )
        return None
    m = _AVG_PRICE_RE.search(resp.text)
    if not m or m.group(1) != str(good_id):
        return None
    avg_price = int(m.group(2))
    name_m = _H3_RE.search(resp.text)
    name = name_m.group(1).strip() if name_m else f"good_{good_id}"
    return name, avg_price


def fetch_kr_price_go(cutoff: date) -> pd.DataFrame | None:
    session = _session()

    inspect_date = _latest_inspect_date(session)
    if inspect_date is None:
        logger.warning("[%s] could not resolve latest inspection date", _SOURCE_KEY)
        return None
    if inspect_date <= cutoff:
        logger.info(
            "[%s] no new inspection date (latest=%s, cutoff=%s)",
            _SOURCE_KEY,
            inspect_date,
            cutoff,
        )
        return None

    small_classes = _small_classes(session)
    if not small_classes:
        logger.warning("[%s] item taxonomy fetch returned nothing", _SOURCE_KEY)
        return None

    # (goodSmlclsCode, group HIGH_CODE, goodId) triples to fetch.
    targets: list[tuple[str, str, str]] = []
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {
            pool.submit(_good_ids, session, sc["CODE"]): sc for sc in small_classes
        }
        for fut in as_completed(futures):
            sc = futures[fut]
            try:
                goods = fut.result()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[%s] goodId lookup failed for %s: %s", _SOURCE_KEY, sc["CODE"], exc
                )
                continue
            for g in goods:
                targets.append((sc["CODE"], sc["HIGH_CODE"], str(g["CODE"])))

    ts = get_scrape_ts()
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {
            pool.submit(_fetch_one_avg, session, sml, grp, gid, inspect_date): gid
            for sml, grp, gid in targets
        }
        for fut in as_completed(futures):
            result = fut.result()
            if result is None:
                continue
            name, price = result
            if not 0 < price < 10_000_000:
                logger.warning(
                    "[%s] implausible price %s for %r — dropping",
                    _SOURCE_KEY,
                    price,
                    name,
                )
                continue
            row = {
                "observation_date": inspect_date.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": name,
                "price_local": float(price),
                "currency": _CURRENCY,
                "unit": "each",
                "source_url": _LIST_URL,
                "notes": "nationwide all-outlet average (전국 전체 판매점 평균)",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    logger.info(
        "[%s] %d rows for inspect_date=%s (targets=%d)",
        _SOURCE_KEY,
        len(rows),
        inspect_date,
        len(targets),
    )
    return pd.DataFrame(rows) if rows else None
