"""Taiwan MOA agricultural wholesale prices — full daily catalogue across markets.

The Ministry of Agriculture open-data platform (data.moa.gov.tw) publishes daily
transaction prices for four commodity families through separate endpoints, each
with its own schema:

  produce  FarmTransData  UnitId=037 — 900+ fruit/veg crops (and cut flowers) by market
  hog      AnimalTransData UnitId=026 — live hogs by market (NT$/kg liveweight)
  sheep    SheepTransData  UnitId=276 — goats & sheep by product & market
  poultry  PoultryTransBoiledChickenData UnitId=056 — broiler chicken + eggs (national)

The hog/sheep/poultry endpoints cover the COICOP live-animal leaves (01.1.2.1.x)
that retail never carries; the produce endpoint covers the fresh fruit/veg
sourcing gaps. This fetcher is general on purpose — it pulls every commodity
from every endpoint, not just the missing leaves, and lets the downstream
division-01 classifier gate non-food rows (e.g. the cut flowers in the produce
feed).

Each endpoint returns its most-recent window newest-first (capped ~5.5k–10k
rows), so incremental daily runs accumulate history; a first run only sees the
last few days for the high-cardinality produce feed. Prices are NT$/kg; the
per-market origin is kept in `notes` and folded into the dedup hash so the
`item_name` stays a clean product string for the embedder. COICOP is deferred.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://data.moa.gov.tw/Service/OpenData/FromM"
_COUNTRY = "Taiwan"
_CURRENCY = "TWD"
_SOURCE_KEY = "tw_moa_wholesale"
_UNIT = "kg"
_IDENT = ["source_key", "observation_date", "item_name", "market"]
_CLOSED = {"休市", "", None}

# Hand-curated COICOP 2018 leaf for the Taiwan MOA feeds, built by enumerating
# all 1,202 distinct item_names in the collected catalogue (2026-09-11).
# Produce item_names are "作物-品種"; the cultivar after the hyphen collapses to
# the same leaf, so `_COICOP_BY_CROP` is keyed on the crop prefix and
# `_COICOP_EXACT` holds the cases where the suffix changes it (dried persimmon,
# cassava, dried longan, shallots, roasted groundnut, kelp) plus the three
# non-produce endpoints. Emitted as the row's `coicop_code` for classify.py's
# narrow_source short-circuit; the manifest stays
# `coicop_classification: classifier` so the rows keep reaching the corpus.
#
# Audited against the production classifier: 95.2% row agreement; the residual
# disagreements are mostly leafy-vegetable convention calls, with 5 outright
# errors (fresh 橄欖 -> PRESERVED olives, 柿餅 dried persimmon -> fresh
# persimmon, 樹薯 cassava -> yams).
_COICOP_EXACT: dict[str, str] = {
    '努比亞雜交閹公羊': '01.1.2.1.3',
    '女羊': '01.1.2.1.3',
    '敏豆-翼豆': '01.1.7.3.9',
    '柿子-柿餅': '01.1.6.7.9',
    '毛豬 (live hog)': '01.1.2.1.2',
    '海菜-水蓮': '01.1.7.1.9',
    '海菜-海帶': '01.1.7.4.6',
    '海菜-龍鬚菜': '01.1.7.4.6',
    '白肉雞(1.75-1.95Kg)': '01.1.2.1.4',
    '白肉雞(2.0Kg以上)': '01.1.2.1.4',
    '白肉雞(門市價高屏)': '01.1.2.1.4',
    '荸薺-加工': '01.1.7.9.9',
    '落花生-熟': '01.1.6.9.4',
    '蓮藕-蓮子': '01.1.6.8.9',
    '薯蕷-樹薯': '01.1.7.5.3',
    '規格外羊': '01.1.2.1.3',
    '豌豆-豌豆苗': '01.1.7.1.9',
    '閹公羊': '01.1.2.1.3',
    '隼人瓜-瓜苗': '01.1.7.1.9',
    '雜柑-其他': '01.1.6.2.9',
    '雜柑-桔子': '01.1.6.2.4',
    '雜柑-檸檬': '01.1.6.2.2',
    '雜柑-無子檸檬': '01.1.6.2.2',
    '雜柑-進口': '01.1.6.2.9',
    '雜柑-黃金檸檬': '01.1.6.2.2',
    '雞蛋(大運輸價)': '01.1.4.8.1',
    '雞蛋(產地價)': '01.1.4.8.1',
    '青蔥-紅蔥頭': '01.1.7.4.3',
    '龍眼-龍眼乾帶殼': '01.1.6.7.9',
}

_COICOP_BY_CROP: dict[str, str] = {
    '九層塔': '01.1.9.4.0',
    '其他菇類': '01.1.7.4.5',
    '冬瓜': '01.1.7.2.5',
    '包心白': '01.1.7.1.2',
    '包心白菜': '01.1.7.1.2',
    '半天筍': '01.1.7.1.9',
    '南瓜': '01.1.7.2.5',
    '大蒜': '01.1.7.4.2',
    '奇異果': '01.1.6.5.2',
    '小番茄': '01.1.7.2.4',
    '小白菜': '01.1.7.1.9',
    '山竹': '01.1.6.1.5',
    '山蘇葉': '01.1.7.1.9',
    '巴西利': '01.1.9.4.0',
    '扁蒲': '01.1.7.2.5',
    '敏豆': '01.1.7.3.2',
    '晚香玉筍': '01.1.7.1.9',
    '木瓜': '01.1.6.1.6',
    '朴菜': '01.1.7.1.9',
    '李': '01.1.6.3.6',
    '杏鮑菇': '01.1.7.4.5',
    '柑橘': '01.1.6.2.4',
    '柚子': '01.1.6.2.1',
    '柳松菇': '01.1.7.4.5',
    '柿子': '01.1.6.5.5',
    '桃子': '01.1.6.3.5',
    '桶筍': '01.1.7.9.9',
    '梨': '01.1.6.3.2',
    '棗子': '01.1.6.5.9',
    '椰子': '01.1.6.1.8',
    '楊桃': '01.1.6.1.9',
    '楊梅': '01.1.6.4.9',
    '榨菜': '01.1.7.9.9',
    '榴槤': '01.1.6.1.9',
    '榴槤蜜': '01.1.6.1.9',
    '橄欖': '01.1.6.5.9',
    '櫻桃': '01.1.6.3.4',
    '毛豆': '01.1.7.3.5',
    '油菜': '01.1.7.1.9',
    '波蘿蜜': '01.1.6.1.9',
    '洋菇': '01.1.7.4.5',
    '洋蔥': '01.1.7.4.3',
    '洋香瓜': '01.1.6.5.3',
    '濕木耳': '01.1.7.4.5',
    '濕香菇': '01.1.7.4.5',
    '火龍果': '01.1.6.1.9',
    '熟筍': '01.1.7.9.9',
    '牛蒡': '01.1.7.4.9',
    '牛頭茄': '01.1.7.2.3',
    '玉米': '01.1.7.4.8',
    '珊瑚菇': '01.1.7.4.5',
    '甘蔗': '01.1.6.5.9',
    '甘薯': '01.1.7.5.2',
    '甘薯葉': '01.1.7.1.9',
    '甘藍': '01.1.7.1.2',
    '甜椒': '01.1.7.2.1',
    '甜橙': '01.1.6.2.3',
    '甜瓜': '01.1.6.5.3',
    '番石榴': '01.1.6.1.5',
    '番茄': '01.1.7.2.4',
    '百香果': '01.1.6.1.9',
    '皇宮菜': '01.1.7.1.9',
    '石蓮花': '01.1.7.1.9',
    '秀珍菇': '01.1.7.4.5',
    '竹筍': '01.1.7.1.9',
    '筍乾': '01.1.7.7.0',
    '筍片': '01.1.7.9.9',
    '筍絲': '01.1.7.9.9',
    '筍茸': '01.1.7.1.9',
    '紅毛丹': '01.1.6.1.9',
    '紅鳳菜': '01.1.7.1.9',
    '紅龍果': '01.1.6.1.9',
    '絲瓜': '01.1.7.2.5',
    '羅勒': '01.1.9.4.0',
    '胡瓜': '01.1.7.2.2',
    '胡蘿蔔': '01.1.7.4.1',
    '芋': '01.1.7.5.5',
    '芒果': '01.1.6.1.5',
    '芥菜': '01.1.7.1.9',
    '芥藍菜': '01.1.7.1.9',
    '芫荽': '01.1.9.4.0',
    '花椰菜': '01.1.7.1.3',
    '花胡瓜': '01.1.7.2.2',
    '芹菜': '01.1.7.1.9',
    '芽菜類': '01.1.7.4.9',
    '苦瓜': '01.1.7.2.9',
    '茄子': '01.1.7.2.3',
    '茭白筍': '01.1.7.1.9',
    '茴香': '01.1.7.1.9',
    '茼蒿': '01.1.7.1.9',
    '草莓': '01.1.6.4.5',
    '草菇': '01.1.7.4.5',
    '荔枝': '01.1.6.1.9',
    '荸薺': '01.1.7.5.9',
    '莧菜': '01.1.7.1.9',
    '菜豆': '01.1.7.3.2',
    '菠菜': '01.1.7.1.5',
    '菱角': '01.1.7.5.9',
    '菾菜': '01.1.7.1.9',
    '萊豆': '01.1.7.3.1',
    '萵苣菜': '01.1.7.1.4',
    '落花生': '01.1.6.8.8',
    '葡萄': '01.1.6.5.1',
    '葡萄柚': '01.1.6.2.1',
    '蓮藕': '01.1.7.5.9',
    '蓮霧': '01.1.6.1.9',
    '蕎頭': '01.1.7.4.4',
    '蕨菜': '01.1.7.1.9',
    '蕹菜': '01.1.7.1.9',
    '薑': '01.1.9.4.0',
    '薯蕷': '01.1.7.5.4',
    '藍莓': '01.1.6.4.6',
    '藤川七': '01.1.7.1.9',
    '蘆筍': '01.1.7.1.1',
    '蘋果': '01.1.6.3.1',
    '蘿蔔': '01.1.7.4.9',
    '蘿蔔乾': '01.1.7.7.0',
    '虎豆': '01.1.7.3.1',
    '蛋黃果': '01.1.6.1.9',
    '蠔菇': '01.1.7.4.5',
    '西洋菜': '01.1.7.1.9',
    '西瓜': '01.1.6.5.4',
    '豆薯': '01.1.7.5.9',
    '豌豆': '01.1.7.3.3',
    '越瓜': '01.1.7.2.9',
    '辣椒': '01.1.7.2.1',
    '酪梨': '01.1.6.1.1',
    '醃瓜': '01.1.7.9.9',
    '釋迦': '01.1.6.1.9',
    '金絲菇': '01.1.7.4.5',
    '金針筍': '01.1.7.1.9',
    '隼人瓜': '01.1.7.2.9',
    '雪里紅': '01.1.7.1.9',
    '青江白菜': '01.1.7.1.9',
    '青花苔': '01.1.7.1.3',
    '青蔥': '01.1.7.4.4',
    '韭菜': '01.1.7.4.4',
    '香茅': '01.1.9.4.0',
    '香蕉': '01.1.6.1.2',
    '馬鈴薯': '01.1.7.5.1',
    '高梁': '01.1.1.1.3',
    '鳳梨': '01.1.6.1.7',
    '鴻喜菇': '01.1.7.4.5',
    '鹹菜': '01.1.7.9.9',
    '黃秋葵': '01.1.7.2.6',
    '黃金果': '01.1.6.1.9',
    '黑甜仔菜': '01.1.7.1.9',
    '龍眼': '01.1.6.1.9',
}

# Cut flowers, foliage and ornamentals: 712 of the 1,202 item names and ~26% of
# this feed's rows. The FarmTransData endpoint is a flower auction as much as a
# produce auction, and none of it is in COICOP 01/02. Listed explicitly so the
# absence of a code is a recorded decision rather than a hole in the crop table.
_NON_FOOD_CROPS: frozenset[str] = frozenset({
    'LA百合', 'OT大連', 'OT帕芳多', 'OT帕雷諾', 'OT曼尼薩', 'OT瑪丹娜', 'OT百合', 'OT競爭者', 'OT紅福特',
    'OT試金石', '五彩千年木', '仙丹花', '伯利恆之星', '八卦草(黃河)', '八角金盤', '其他花類', '其它花卉', '切葉類',
    '初雪草', '劍蘭', '千代蘭', '千日紅', '半天花', '卡斯比亞', '向日葵', '唐棉', '嘉蘭(火焰百合)', '垂雞冠', '壽松',
    '夕霧草', '夜來香', '大文心蘭', '大理花', '大菊', '天堂鳥', '姬百合', '射干', '專利染色水燭花', '小天堂鳥', '小菊',
    '小飛燕草', '尤加利葉', '康乃馨', '扁柏', '拖鞋蘭', '文心蘭', '斑葉蘭', '新文竹', '新西蘭株', '新西蘭葉', '星辰花',
    '星點木', '春樹蘭', '松蟲草', '染大菊', '染小菊', '柔麗絲', '槍型雞冠花', '樊花', '樹蘭', '檸檬綠文心蘭', '水仙百合',
    '水晶花', '水晶香水', '水燭葉', '波斯菊', '洋吉梗', '洋桔梗', '洋甘菊', '深山櫻', '滿天星', '火鶴花', '火鶴葉',
    '玉羊齒', '玉蘭花', '玫瑰', '珊瑚鳳梨', '白孔雀', '白日草', '白竹', '百合', '百合竹', '睡蓮', '石斛蘭', '石玫瑰',
    '石蒜', '秀線', '粉孔雀', '紅竹', '紅薑花', '紐西蘭麻', '紫孔雀', '綠春蘭葉', '繡球撫子', '繡球花', '腎藥蘭',
    '花竹', '茉莉花', '萬代蘭', '萬壽菊', '葉蘭', '蓮花竹', '薑荷花', '藍星花', '蘆筍草', '蘭花', '虎尾花', '虎斑木葉',
    '蜘蛛蘭', '蝴蝶蘭', '補血草', '觀花鳳梨花', '觀音蓮', '變色葉', '貝殼花', '進口丹頂(蔥花)', '進口其它花卉', '進口切葉類',
    '進口卡斯比亞', '進口大菊', '進口大飛燕草', '進口小可愛', '進口小菊', '進口小蒼蘭', '進口小飛燕草', '進口帝王花', '進口康乃馨',
    '進口星辰花', '進口染色大菊', '進口染色小菊', '進口棉花', '進口樺木(假葉)', '進口水仙百合', '進口水晶花', '進口泡盛草',
    '進口海芋', '進口滿天星', '進口牡丹花', '進口狐尾百合', '進口玫瑰', '進口石斛蘭', '進口石蒜', '進口繡球花', '進口臘梅',
    '進口花材', '進口虎頭蘭', '進口金魚草', '進口針墊花', '進口非洲鬱金香', '進口風鈴花', '進口香水百合', '進口高山羊齒',
    '進口鬱金香', '進口龍膽', '重瓣百合', '野薑花', '金針花', '金魚草', '銀蘆', '鋸齒蔓綠絨葉', '鐵砲百合', '雞冠花',
    '雪松', '雲龍柳', '電信蘭葉', '青竹', '非洲菊', '香水文心蘭', '香水百合', '高山羊齒', '鶴焦', '鶴蕉紅美人', '麒麟草',
    '黃征木', '黃梔花', '黃椰心葉', '黃金鳥', '龍文蘭'
})


def _coicop_for(item_name: str) -> str | None:
    """Curated leaf for a MOA item, or None to defer to the classifier."""
    hit = _COICOP_EXACT.get(item_name)
    if hit:
        return hit
    crop = item_name.split("-")[0]
    if crop in _NON_FOOD_CROPS:
        return None
    return _COICOP_BY_CROP.get(crop)


def _roc_compact(s: str) -> date | None:
    # "1150804" -> 2026-08-04
    s = (s or "").strip()
    if len(s) < 7 or not s.isdigit():
        return None
    try:
        return date(int(s[:-4]) + 1911, int(s[-4:-2]), int(s[-2:]))
    except ValueError:
        return None


def _roc_dotted(s: str) -> date | None:
    # "115.08.05" -> 2026-08-05
    parts = (s or "").strip().split(".")
    if len(parts) != 3:
        return None
    try:
        return date(int(parts[0]) + 1911, int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def _iso(s: str) -> date | None:
    try:
        return date.fromisoformat((s or "").strip()[:10])
    except ValueError:
        return None


def _slash(s: str) -> date | None:
    try:
        return datetime.strptime((s or "").strip(), "%Y/%m/%d").date()
    except ValueError:
        return None


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if 0 < f < 1_000_000 else None


def _parse_produce(records: list, cutoff: date) -> list[dict]:
    out = []
    for r in records:
        crop = (r.get("作物名稱") or "").strip()
        if crop in _CLOSED:
            continue
        d = _roc_dotted(r.get("交易日期"))
        price = _num(r.get("平均價"))
        if d is None or price is None or d <= cutoff:
            continue
        out.append(
            {
                "obs_date": d,
                "market": (r.get("市場名稱") or "").strip(),
                "item_name": crop,
                "price": price,
                "note": (
                    f"produce; high={r.get('上價')} mid={r.get('中價')} low={r.get('下價')} "
                    f"vol={r.get('交易量')}"
                ),
            }
        )
    return out


def _parse_hog(records: list, cutoff: date) -> list[dict]:
    out = []
    for r in records:
        d = _roc_compact(r.get("交易日期"))
        price = _num(r.get("成交頭數-平均價格"))
        if d is None or price is None or d <= cutoff:
            continue
        out.append(
            {
                "obs_date": d,
                "market": (r.get("市場名稱") or "").strip(),
                "item_name": "毛豬 (live hog)",
                "price": price,
                "note": (
                    f"live hog auction; avg_weight={r.get('成交頭數-平均重量')} "
                    f"head={r.get('成交頭數-總數')}"
                ),
            }
        )
    return out


def _parse_sheep(records: list, cutoff: date) -> list[dict]:
    out = []
    for r in records:
        name = (r.get("productName") or "").strip()
        d = _iso(r.get("transDate"))
        price = _num(r.get("avgPrice"))
        if not name or d is None or price is None or d <= cutoff:
            continue
        out.append(
            {
                "obs_date": d,
                "market": (r.get("name") or r.get("shortName") or "").strip(),
                "item_name": name,
                "price": price,
                "note": (
                    f"sheep/goat auction; avg_weight={r.get('avgWeight')} "
                    f"qty={r.get('quantity')} high={r.get('highestPrice')}"
                ),
            }
        )
    return out


_POULTRY_SKIP = {"日期", "農曆"}


def _parse_poultry(records: list, cutoff: date) -> list[dict]:
    out = []
    for r in records:
        d = _slash(r.get("日期"))
        if d is None or d <= cutoff:
            continue
        for col, val in r.items():
            if col in _POULTRY_SKIP:
                continue
            price = _num(val)
            if price is None:
                continue
            out.append(
                {
                    "obs_date": d,
                    "market": "",
                    "item_name": col.strip(),
                    "price": price,
                    "note": "poultry/egg national quote",
                }
            )
    return out


_ENDPOINTS = [
    ("FarmTransData", "037", _parse_produce),
    ("AnimalTransData", "026", _parse_hog),
    ("SheepTransData", "276", _parse_sheep),
    ("PoultryTransBoiledChickenData", "056", _parse_poultry),
]


def _load(session, path: str, unit_id: str) -> list | None:
    url = f"{_BASE}/{path}.aspx?UnitId={unit_id}&IsTransData=1"
    try:
        resp = session.get(url, timeout=200)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[%s] %s (UnitId=%s) fetch failed: %s", _SOURCE_KEY, path, unit_id, exc
        )
        return None
    try:
        return json.loads(resp.content.decode("utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning(
            "[%s] %s (UnitId=%s) parse failed: %s", _SOURCE_KEY, path, unit_id, exc
        )
        return None


def fetch_tw_moa_wholesale(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120 Safari/537.36"
        }
    )
    ts = get_scrape_ts()
    rows: list[dict] = []
    seen: set = set()
    for path, unit_id, parser in _ENDPOINTS:
        records = _load(session, path, unit_id)
        if not records:
            continue
        parsed = parser(records, cutoff)
        for p in parsed:
            row = {
                "observation_date": p["obs_date"].isoformat(),
                "period_kind": "daily",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": p["item_name"],
                "coicop_code": _coicop_for(p["item_name"]),
                "price_local": round(p["price"], 2),
                "currency": _CURRENCY,
                "unit": _UNIT,
                "source_url": f"{_BASE}/{path}.aspx?UnitId={unit_id}",
                "notes": f"wholesale {p['note']}; market={p['market']}",
                "scrape_ts": ts,
                "market": p["market"],
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            key = row["observation_hash"]
            if key in seen:
                continue
            seen.add(key)
            del row["market"]
            rows.append(row)
        logger.info(
            "[%s] %s (UnitId=%s): %d rows", _SOURCE_KEY, path, unit_id, len(parsed)
        )
    logger.info("[%s] %d rows total (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
