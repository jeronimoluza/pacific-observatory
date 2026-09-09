"""World Bank RTDI food prices (microdata.worldbank.org) — shared EAP fetcher.

The Real-Time Development Indicators collection publishes monthly food price
levels per commodity per market, reaching back to 2007 — roughly a decade
further than anything the retail scrapers can reach, since Common Crawl and
Wayback both thin out badly before 2016. Four EAP countries are covered:
Indonesia, Lao PDR, Myanmar and the Philippines.

Unlike WFP, this feed carries its COICOP **per item**, from ``_ITEMS`` below,
rather than deferring to the classifier. Two reasons. The vocabulary is a closed
controlled set of 33 (country, ticker) pairs, small enough to map by hand and
audit by eye. And the tickers are bare commodity nouns — ``rice``, ``oil`` —
which is the input the classifier is weakest on, having no brand, pack size or
retailer context to work from.

**The mapping must key on (iso3, ticker), never ticker alone.** One token covers
different products in different countries: ``oil`` is vegetable in Indonesia,
soybean in Lao PDR and palm in Myanmar — three distinct leaves of 01.1.5. The
``full_name`` column in each study's ticker_info is what disambiguates them, and
it is recorded beside every entry below.

Three columns look usable and are not:

- ``food_price_index`` is an INDEX (Jan 2018 = 1), not a level. It is the only
  ticker present in all 37 RTFP studies, so it is also the easiest to include by
  accident. Excluded by omission from ``_ITEMS``.
- bare ``<ticker>`` columns are the raw survey observations, sparse by design
  (14,698 of 52,628 for Indonesian rice). The ``c_<ticker>`` close series is the
  dense model-completed estimate, and is what we read.
- ``exchange_rate_unofficial`` rides in every country and is not a consumption
  good at all.

Lao PDR's two fuel tickers are likewise omitted: they are division 07, which the
build's division-01/02 filter would drop anyway.

Units are only partly usable. "KG" and "L" normalise to kg and lt; "Unit",
which prices eggs singly in Lao PDR and the Philippines, resolves to nothing,
so those two entries produce observations but no unit value.

Per-market rows are kept rather than collapsed to a national average. They share
one ``input_hash`` — identity is (item_name, source_url), and the URL is the
study, so every market of a given item resolves to a single classification —
while all of them survive into the observations frame, where they give each
(leaf, country, unit) cell real support instead of one row a month.
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://microdata.worldbank.org"
_IDENT = ["source_key", "observation_date", "item_name", "subnational_area"]

# Every weekly vintage is exposed at once and the newest is listed first;
# three files per vintage means the data file is always within the first few.
_MAX_PROBES = 12

# iso3 -> (display country, NADA IDNO, numeric catalog id)
_STUDIES: dict[str, tuple[str, str, int]] = {
    "idn": ("Indonesia", "IDN_2021_RTFP_v02_M", 6166),
    "lao": ("Lao PDR", "LAO_2021_RTFP_v02_M", 4496),
    "mmr": ("Myanmar", "MMR_2021_RTFP_v02_M", 4501),
    "phl": ("Philippines", "PHL_2021_RTFP_v02_M", 6172),
}

# (iso3, ticker) -> (COICOP leaf, unit, the study's own full_name)
# Every code is a deepest leaf of the repo taxonomy. A code that is not a leaf
# fails `coicop_codes.is_narrow` SILENTLY and falls through to the classifier,
# so `test_wb_rtdi_prices` asserts every entry here resolves.
_ITEMS: dict[tuple[str, str], tuple[str, str, str]] = {
    # --- Indonesia -------------------------------------------------------
    ("idn", "eggs"): ("01.1.4.8.1", "KG", "Eggs"),
    ("idn", "garlic"): ("01.1.7.4.2", "KG", "Garlic (medium)"),
    ("idn", "meat_beef"): ("01.1.2.2.1", "KG", "Meat (beef, first quality)"),
    ("idn", "meat_chicken"): ("01.1.2.2.4", "KG", "Meat (chicken)"),
    ("idn", "meat_chicken_broiler"): ("01.1.2.2.4", "KG", "Meat (chicken, broiler)"),
    ("idn", "oil"): ("01.1.5.1.9", "KG", "Oil (vegetable)"),
    ("idn", "onions"): ("01.1.7.4.3", "KG", "Onions (shallot, medium)"),
    ("idn", "rice"): ("01.1.1.1.2", "KG", "Rice (medium quality)"),
    ("idn", "sugar"): ("01.1.8.1.1", "KG", "Sugar (local)"),
    # --- Lao PDR ---------------------------------------------------------
    ("lao", "eggs"): ("01.1.4.8.1", "Unit", "Eggs"),
    ("lao", "fish_catfish"): ("01.1.3.1.1", "KG", "Fish (catfish)"),
    ("lao", "fish_tilapia"): ("01.1.3.1.1", "KG", "Fish (tilapia, farmed)"),
    ("lao", "garlic"): ("01.1.7.4.2", "KG", "Garlic (small)"),
    ("lao", "meat_beef"): ("01.1.2.2.1", "KG", "Meat (beef, second quality)"),
    # Buffalo is a bovine, so it shares the bovine-meat leaf with beef.
    ("lao", "meat_buffalo"): ("01.1.2.2.1", "KG", "Meat (buffalo, first quality)"),
    ("lao", "meat_chicken"): ("01.1.2.2.4", "KG", "Meat (chicken)"),
    ("lao", "meat_pork"): ("01.1.2.2.2", "KG", "Meat (pork, second quality)"),
    ("lao", "oil"): ("01.1.5.1.4", "L", "Oil (soybean)"),
    ("lao", "rice"): ("01.1.1.1.2", "KG", "Rice (glutinous, unmilled)"),
    ("lao", "sugar"): ("01.1.8.1.1", "KG", "Sugar (brown)"),
    # --- Myanmar ---------------------------------------------------------
    ("mmr", "oil"): ("01.1.5.1.2", "L", "Oil (palm)"),
    ("mmr", "pulses"): ("01.1.7.6.9", "KG", "Pulses"),
    ("mmr", "rice"): ("01.1.1.1.2", "KG", "Rice (low quality)"),
    ("mmr", "salt"): ("01.1.9.3.1", "KG", "Salt"),
    # --- Philippines -----------------------------------------------------
    ("phl", "beans"): ("01.1.7.6.1", "KG", "Beans (mung)"),
    ("phl", "cabbage"): ("01.1.7.1.2", "KG", "Cabbage"),
    ("phl", "carrots"): ("01.1.7.4.1", "KG", "Carrots"),
    ("phl", "eggs"): ("01.1.4.8.1", "Unit", "Eggs"),
    ("phl", "garlic"): ("01.1.7.4.2", "KG", "Garlic"),
    ("phl", "onions"): ("01.1.7.4.3", "KG", "Onions (red)"),
    ("phl", "potatoes"): ("01.1.7.5.2", "KG", "Sweet potatoes"),
    ("phl", "rice"): ("01.1.1.1.2", "KG", "Rice (regular, milled)"),
    ("phl", "tomatoes"): ("01.1.7.2.4", "KG", "Tomatoes"),
}

# Units are passed through as the study writes them, the way the WFP fetcher
# does: `declared_unit.parse_declared_unit` folds case, so "KG" -> kg and
# "L" -> lt without help.
#
# "Unit" is the exception and it does NOT resolve -- no count token does, since
# parse_declared_unit only covers mass, volume and length. The two per-egg
# entries below (lao, phl) will therefore carry a correct COICOP leaf but no
# standard unit, so they yield observations without unit values and will not
# fill a grid cell until a count basis exists. They are mapped rather than
# dropped because the price is real and the leaf is right.


def _resolve_zip_url(session, catalog_id: int) -> str | None:
    """Return the newest market-panel zip URL for a study, accepting terms first.

    Two things make this fiddlier than it looks. The download links only render
    after a click-through POST carrying a CSRF token. And a study exposes EVERY
    weekly vintage at once -- 317 resource ids for Lao PDR alone -- so the newest
    has to be picked deliberately rather than by taking whatever comes first.

    The filename lives in `content-disposition`, not in the page: every link's
    visible text is just the URL again. So candidates are probed with HEAD, in
    page order, which puts the newest vintage first.

    The match must be `_RTFP_mkt_`, not `_mkt_`. Each vintage ships three files
    whose names all contain `_mkt_`, and the two decoys -- `_RTP_details_mkt_`
    and `_RTP_ticker_info_mkt_` -- are listed BEFORE the data file and are a few
    hundred bytes each.
    """
    page = f"{_BASE}/index.php/catalog/{catalog_id}/get-microdata"
    try:
        got = session.get(page, timeout=90)
        got.raise_for_status()
        token = re.search(r'name="ncsrf"[^>]*value="([0-9a-fA-F]+)"', got.text)
        html = got.text
        if token:
            posted = session.post(
                page, data={"ncsrf": token.group(1), "accept": "Accept"}, timeout=90
            )
            posted.raise_for_status()
            html = posted.text
    except Exception as exc:  # noqa: BLE001 — network or markup change
        logger.warning("[wb_rtdi] terms acceptance failed for %s: %s", catalog_id, exc)
        return None

    seen: list[str] = []
    for rid in re.findall(rf"catalog/{catalog_id}/download/(\d+)", html):
        if rid not in seen:
            seen.append(rid)
    if not seen:
        logger.warning("[wb_rtdi] no download links for catalog %s", catalog_id)
        return None

    for rid in seen[:_MAX_PROBES]:
        url = f"{_BASE}/index.php/catalog/{catalog_id}/download/{rid}"
        try:
            head = session.head(url, timeout=60, allow_redirects=True)
            name = re.search(
                r"filename\*?=(?:UTF-8'')?\"?([^\";]+)",
                head.headers.get("content-disposition", ""),
            )
        except Exception:  # noqa: BLE001 — probe failure is not fatal
            continue
        if name and "_RTFP_mkt_" in name.group(1) and name.group(1).endswith(".zip"):
            logger.info("[wb_rtdi] catalog %s -> %s", catalog_id, name.group(1).strip())
            return url
    logger.warning(
        "[wb_rtdi] no _RTFP_mkt_ zip in the first %d of %d resources for catalog %s",
        _MAX_PROBES,
        len(seen),
        catalog_id,
    )
    return None


def _market_frame(blob: bytes) -> pd.DataFrame | None:
    """Extract the market-level CSV from a study zip."""
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = [
            n
            for n in zf.namelist()
            if n.lower().endswith(".csv")
            and "_mkt_" in n
            and "details" not in n.lower()
            and "ticker" not in n.lower()
        ]
        if not names:
            return None
        with zf.open(names[0]) as fh:
            return pd.read_csv(fh, low_memory=False)


def _rows(df: pd.DataFrame, iso3: str, country: str, url: str, cutoff: date) -> list[dict]:
    source_key = f"wb_rtdi_{iso3}"
    ts = get_scrape_ts()
    dates = pd.to_datetime(df["price_date"], errors="coerce")
    keep = dates.notna() & (dates.dt.date >= cutoff)
    df, dates = df[keep], dates[keep]
    currency = str(df["currency"].dropna().iloc[0]) if len(df["currency"].dropna()) else None

    out: list[dict] = []
    for (i3, ticker), (code, unit_raw, full_name) in _ITEMS.items():
        if i3 != iso3:
            continue
        col = f"c_{ticker}"
        if col not in df.columns:
            logger.warning("[%s] declared ticker %s absent from panel", source_key, ticker)
            continue
        price = pd.to_numeric(df[col], errors="coerce")
        ok = price.notna() & (price > 0)
        if not ok.any():
            continue
        sub = df[ok]
        for obs_date, market, value in zip(
            dates[ok].dt.date, sub.get("mkt_name", pd.Series(dtype=str)), price[ok]
        ):
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly",
                "country": country,
                "subnational_area": str(market) if pd.notna(market) else None,
                "source_key": source_key,
                # Curated per item -- see the module docstring.
                "coicop_code": code,
                "item_name": full_name,
                "price_local": round(float(value), 4),
                "currency": currency,
                "unit": unit_raw,
                "source_url": url,
                "notes": f"WB RTDI monthly close; ticker={ticker}; market-level estimate",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            out.append(row)
    return out


def _fetch(cutoff: date, *, iso3: str) -> pd.DataFrame | None:
    country, _idno, catalog_id = _STUDIES[iso3]
    source_key = f"wb_rtdi_{iso3}"
    session = get_session()
    url = _resolve_zip_url(session, catalog_id)
    if not url:
        return None
    try:
        resp = session.get(url, timeout=300)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] zip fetch failed: %s", source_key, exc)
        return None
    frame = _market_frame(resp.content)
    if frame is None or frame.empty:
        logger.warning("[%s] no market CSV inside the study zip", source_key)
        return None
    rows = _rows(frame, iso3, country, f"{_BASE}/index.php/catalog/{catalog_id}", cutoff)
    logger.info("[%s] %d market-month rows (cutoff=%s)", source_key, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None


def fetch_wb_rtdi_idn(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="idn")


def fetch_wb_rtdi_lao(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="lao")


def fetch_wb_rtdi_mmr(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="mmr")


def fetch_wb_rtdi_phl(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="phl")
