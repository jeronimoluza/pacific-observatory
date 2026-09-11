"""Macao municipal-market (街市) daily fresh-food prices, per market stall
block, published by the Consumer Council (消費者委員會) on behalf of the
Municipal Affairs Bureau (市政署 / IAM).

NOT the same source as the sibling `consumer_price_station.py`. That one reads
the Council's *supermarket* comparison (api03.consumer.gov.mo, ~598 packaged
grocery lines, price RANGE across surveyed supermarkets, COICOP left to the
classifier). This one reads the Council's *municipal market* feed, an entirely
separate ASP.NET WebForms app at `consumer.dsedt.gov.mo/api02/`, which carries
exactly the fresh categories the supermarket feed does not: freshwater fish,
saltwater fish, other seafood, pork, beef and fresh vegetables -- 60 items in
a closed, stable vocabulary, priced separately at each of Macao's nine public
markets. The bottom of every page says so: "街市價格資訊由澳門特別行政區政府
市政署提供" (market price information supplied by IAM).

The other URL the discovery run surfaced for this data, the 街市通 SPA at
`app.iam.gov.mo/marketinfo/`, is IAM's own front end over the same numbers.
Its JSON API (`/marketinfo/goods/getGoodsCategory`, `/goodsPrice/
getGoodsPriceByMarket`, ...) is a POST-only Spring service whose request
envelope is built inside a webpack bundle and which answers `{}` to a plain
`{"body": {...}}` post. The DSEDT WebForms pages below carry the same per-
market prices with no envelope to reverse-engineer, so they are what this
fetcher reads.

SHAPE (verified live 2026-09-11/12)
-----------------------------------
Three pages, all plain GET, no cookie, no VIEWSTATE round-trip needed:

  MarketCategory.aspx?lan=cn
      Six categories, each as an <a href> carrying `c=<CategoryKey>` and
      `ccn=<Chinese label>`. Read live rather than hardcoded -- the same
      reasoning as stat_uz_avg_prices: the category set is the publisher's
      to change.

  MarketItemLowestPrice.aspx?lan=cn&c=<CategoryKey>&ccn=&pftype=
      One <a> per item per view (today / week), carrying `tn=<Chinese item
      name>` and `s=<Portuguese item name>`.

  MarketPrice?<the item's own href query>
      Per-market prices for that item. Nine market blocks, each rendered
      twice: `mp-cell detaila` = today's price, `mp-cell detailb` = the
      week's average (hidden behind a tab). Each block carries two figures,
      `lp lpa` and `lp lpb`, with the unit as literal text beside them.

`lan=en` is NOT English -- it serves the Portuguese item names, same as
`lan=pt`. `lan=cn` is used so `item_name` matches the manifest's
`language: zh`, and the Portuguese name rides in `notes`.

WHY ONLY `lp lpb` IS READ
-------------------------
`lpa` is denominated in a Chinese customary unit that is NOT constant across
categories: 元/司馬斤 (per catty, 604.8 g) for vegetables, meat and seafood,
but 元/兩 (per tael, 37.8 g) for saltwater fish. Reading `lpa` and calling it
one unit would emit a silent 16x error on the fish rows. `lpb` is 元/公斤
(per kilogram) everywhere, so it is the only figure taken and `unit` is
always "kg". The item-list page's own `lpa`/`lpb` query values are ignored
for the same reason -- and on saltwater fish they are inconsistent with each
other (石斑 shows lpa=4.5, lpb=2.7, which is not any fixed ratio).

Only `detaila` (today) is emitted. `detailb` (week average) covers the same
(item, market, date) key and `period_kind` is not part of PRICE_COLUMNS's
identity, so ingesting both would collide on `observation_hash` -- the same
venue-collision trap documented in stat_uz_avg_prices. Today's snapshot was
chosen because it is the commensurate observation; the weekly average is the
obvious follow-up if a period dimension is ever added.

Markets that do not stock an item render `$---`; those blocks are skipped.

`observation_date` comes from the page's own 更新日期 stamp (the today-price
one, `udate-block today-udate`), not from the request date.

`_COICOP_MAP` stamps a per-ITEM COICOP-2018 leaf while the manifest stays
`coicop_classification: classifier`. That pairing is deliberate, exactly as
in stat_uz_avg_prices: `concatenate`'s `_build_classifier_csv_map` ingests a
fetcher's price_observations.csv ONLY for `classifier` sources, and the
per-row code then rides through as `declared_coicop_codes` and short-circuits
the head in `classify` (`state=narrow_source`, confidence 1.0). Declaring
`source_curated` would remove this file from the corpus altogether.

All 60 items are mapped. Cuts sold as bone / trotter / tendon (豬骨, 豬手,
牛筋) go to 01.1.2.4.0 "Offal, blood and other parts of slaughtered animals"
rather than to the fresh-meat leaves; everything else in Pork/Beef is a
muscle cut. Unmapped items are left uncoded rather than dropped -- under
`classifier` a null coicop_code is legitimate and the head decides.

MEASURED, first run 2026-09-11: 383 rows over 57 items and 8 markets, every
row coded. Three of the 60 items do not reach the corpus, all deliberately:
豬扒 because its per-market page 404s (see `_requote`), 帶子 (scallop) because
it is priced 元/頭 -- per piece, not per weight -- which the unit guard
rejects rather than mislabelling as kg, and 九吐 because no market listed it
on the day. The 元/頭 case is the reason the guard keys on the rendered unit
label instead of trusting the column position.

Emits PriceObservation rows.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://consumer.dsedt.gov.mo/api02/"
_CATEGORY_URL = _BASE + "MarketCategory.aspx?lan=cn"
_COUNTRY = "Macao SAR, China"
_CURRENCY = "MOP"
_SOURCE_KEY = "mo_iam_market_prices"

_IDENT = ["source_key", "observation_date", "subnational_area", "item_name"]

_CAT_RE = re.compile(
    r"href='\./MarketItemLowestPrice\.aspx\?lan=cn&c=([A-Za-z]+)&ccn=([^&]*)&"
)
_ITEM_RE = re.compile(r"href='\./(MarketPrice\?[^']*&t=today[^']*)'")
_TN_RE = re.compile(r"[?&]tn=([^&]*)")
_SN_RE = re.compile(r"[?&]s=([^&]*)")
_CELL_RE = re.compile(r"<div class='mp-cell (detail[ab])[^>]*>(.*?)</div></div></div>", re.S)
_NAME_RE = re.compile(r"class='name bold'>([^<]*)<")
_LPB_RE = re.compile(r"class='lp lpb'>\$([^<]*)<span[^>]*>\(([^)]*)\)")
_UDATE_RE = re.compile(r"class=\"udate-block today-udate\"[^>]*>([^<]*)<")

# Chinese item label (tn) -> COICOP-2018 leaf.
_COICOP_MAP = {
    # 魚類 - 淡水魚 (freshwater fish)
    "大魚": "01.1.3.1.1",
    "鯇魚": "01.1.3.1.1",
    "鯪魚": "01.1.3.1.1",
    "鯽魚": "01.1.3.1.1",
    # 魚類 - 鹹水魚 (saltwater fish)
    "黃腳𩶘": "01.1.3.1.9",
    "馬頭": "01.1.3.1.9",
    "石斑": "01.1.3.1.9",
    "九吐": "01.1.3.1.9",
    "幼鱗撻沙": "01.1.3.1.3",
    "粗鱗撻沙(中型)": "01.1.3.1.3",
    "鱸魚": "01.1.3.1.9",
    "䱽魚": "01.1.3.1.9",
    "紅衫": "01.1.3.1.9",
    "鮫魚": "01.1.3.1.6",
    # 海產品類 (seafood); 魷魚 squid appears in both fish and seafood lists
    "魷魚": "01.1.3.4.4",
    "沙蝦": "01.1.3.4.1",
    "中蝦": "01.1.3.4.1",
    "瀨尿蝦": "01.1.3.4.2",
    "肉蟹": "01.1.3.4.2",
    "青口": "01.1.3.4.3",
    "蟶子": "01.1.3.4.3",
    "帶子": "01.1.3.4.3",
    # 豬肉類 (pork)
    "半肥瘦": "01.1.2.2.2",
    "瘦肉": "01.1.2.2.2",
    "豬𦟌": "01.1.2.2.2",
    "排骨": "01.1.2.2.2",
    "豬腩": "01.1.2.2.2",
    "豬扒": "01.1.2.2.2",
    "柳梅": "01.1.2.2.2",
    "豬肉骨": "01.1.2.2.2",
    "豬手": "01.1.2.4.0",
    "豬骨": "01.1.2.4.0",
    # 牛肉類 (beef)
    "牛腩": "01.1.2.2.1",
    "尾龍扒": "01.1.2.2.1",
    "牛肉": "01.1.2.2.1",
    "牛𦟌": "01.1.2.2.1",
    "牛柳": "01.1.2.2.1",
    "內腿肉": "01.1.2.2.1",
    "冧肉": "01.1.2.2.1",
    "西冷": "01.1.2.2.1",
    "牛筋": "01.1.2.4.0",
    # 新鮮食用蔬菜類 (fresh vegetables)
    "冬瓜": "01.1.7.2.5",
    "節瓜": "01.1.7.2.5",
    "西洋菜": "01.1.7.1.9",
    "莧菜": "01.1.7.1.9",
    "菜心": "01.1.7.1.9",
    "蕹菜": "01.1.7.1.9",
    "芥蘭": "01.1.7.1.9",
    "生菜": "01.1.7.1.4",
    "菠菜": "01.1.7.1.5",
    "西蘭花": "01.1.7.1.3",
    "白菜": "01.1.7.1.2",
    "椰菜": "01.1.7.1.2",
    "馬鈴薯": "01.1.7.5.1",
    "番薯": "01.1.7.5.2",
    "洋葱": "01.1.7.4.3",
    "紅蘿蔔": "01.1.7.4.1",
    "青瓜": "01.1.7.2.2",
    "番茄": "01.1.7.2.4",
}


def _unquote(value: str) -> str:
    from urllib.parse import unquote

    return unquote(value.replace("&amp;", "&"))


def _requote(query: str) -> str:
    """Re-encode an href's query string so every value is fully escaped.

    The page emits its own hrefs only half-escaped: the Portuguese name of
    one pork cut is literally `s=Lombada {Lombo / Costeletas}`, whose raw
    `/` makes IIS route the request to a different path and return 404.
    Round-tripping through unquote + quote(safe="") fixes that without
    hardcoding the offending item.
    """
    from urllib.parse import quote, unquote

    path, _, raw = query.replace("&amp;", "&").partition("?")
    parts = []
    for pair in raw.split("&"):
        key, sep, value = pair.partition("=")
        parts.append(key + sep + quote(unquote(value), safe=""))
    return path + "?" + "&".join(parts)


def _parse_update_date(html: str) -> date | None:
    """The 更新日期 stamp on the today-price block, e.g. '2026/9/12 0:00:03'."""
    m = _UDATE_RE.search(html)
    if not m:
        return None
    m2 = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", m.group(1))
    if not m2:
        return None
    try:
        return date(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
    except ValueError:
        return None


def fetch_mo_iam_market_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    index = session.get(_CATEGORY_URL, timeout=60)
    index.raise_for_status()
    categories = _CAT_RE.findall(index.text)
    if not categories:
        logger.warning("%s: no categories found on %s", _SOURCE_KEY, _CATEGORY_URL)
        return None

    rows: list[dict] = []
    unmapped: set[str] = set()
    for cat_key, cat_label in categories:
        listing_url = (
            _BASE + "MarketItemLowestPrice.aspx?lan=cn&c=%s&ccn=&pftype=" % cat_key
        )
        listing = session.get(listing_url, timeout=60)
        listing.raise_for_status()
        seen: set[str] = set()
        for href in _ITEM_RE.findall(listing.text):
            query = href.replace("&amp;", "&")
            tn = _TN_RE.search(query)
            if not tn:
                continue
            item = _unquote(tn.group(1))
            if item in seen:
                continue
            seen.add(item)
            pt_match = _SN_RE.search(query)
            pt_name = _unquote(pt_match.group(1)) if pt_match else ""

            detail_url = _BASE + _requote(query)
            detail = session.get(detail_url, timeout=60)
            if detail.status_code != 200 or "mp-cell" not in detail.text:
                # The per-market page keys on the item's Portuguese name and
                # will not serve a substitute or a blank one. One pork cut is
                # published as "Lombada {Lombo / Costeletas}", whose raw "/"
                # IIS refuses in any encoding (404 escaped, 404 unescaped),
                # and a wrong/blank `s` returns the site's generic page with
                # no price block at all. Skip rather than fall back to the
                # item-list figures -- those are per-catty/per-tael and are
                # mutually inconsistent on saltwater fish (see docstring).
                logger.warning(
                    "%s: no per-market page for %r (HTTP %s) -- skipping item",
                    _SOURCE_KEY,
                    item,
                    detail.status_code,
                )
                continue
            obs_date = _parse_update_date(detail.text)
            if obs_date is None:
                logger.warning(
                    "%s: no 更新日期 stamp for %r -- skipping", _SOURCE_KEY, item
                )
                continue
            if obs_date <= cutoff:
                continue

            coicop = _COICOP_MAP.get(item)
            if not coicop:
                unmapped.add(item)

            for cell in _CELL_RE.finditer(detail.text):
                kind, block = cell.group(1), cell.group(2)
                if kind != "detaila":  # today's price only -- see module docstring
                    continue
                name = _NAME_RE.search(block)
                price = _LPB_RE.search(block)
                if not name or not price:
                    continue
                raw, unit_label = price.group(1).strip(), price.group(2)
                if "公斤" not in unit_label:
                    logger.warning(
                        "%s: unexpected unit %r for %r -- skipping",
                        _SOURCE_KEY,
                        unit_label,
                        item,
                    )
                    continue
                try:
                    value = float(raw)
                except ValueError:
                    continue  # markets that do not stock the item render "$---"
                if value <= 0:
                    continue
                row = {
                    "observation_date": obs_date.isoformat(),
                    "period_kind": "snapshot",
                    "country": _COUNTRY,
                    "subnational_area": name.group(1).strip(),
                    "source_key": _SOURCE_KEY,
                    "coicop_code": coicop,
                    "item_name": item,
                    "price_local": value,
                    "currency": _CURRENCY,
                    "unit": "kg",
                    "source_url": detail_url,
                    "notes": "category=%s; pt=%s" % (cat_label, pt_name),
                    "scrape_ts": get_scrape_ts(),
                    "observation_hash": None,
                }
                row["observation_hash"] = make_hash(row, _IDENT)
                rows.append(row)

    if unmapped:
        logger.warning(
            "%s: no COICOP mapping for %d item(s): %s",
            _SOURCE_KEY,
            len(unmapped),
            ", ".join(sorted(unmapped)),
        )
    return pd.DataFrame(rows) if rows else None
