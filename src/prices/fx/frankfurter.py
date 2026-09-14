"""Client for api.frankfurter.dev **v2**.

Why this provider, named explicitly: it is keyless, it blends ~84 central
bank / IMF / ECB scrapers with zero commercial vendors, and v2 covers every
currency the price corpus uses back well before the corpus starts.

**v1 and v2 are different APIs, not the same API with more currencies.**
``/v1/currencies`` returns exactly 30 ECB reference currencies and v1's
``/{start}..{end}?symbols=`` path shape returns 404 on v2. v2 uses
``/v2/rates`` with query parameters and returns a flat LIST of records. A
vault note calling Frankfurter "30 ECB currencies, missing exactly the
Pacific" was measuring v1; it does not describe v2.

Operational facts, all verified against the live API:

* The default urllib ``User-Agent`` gets **403**. Send a real one.
* A single unknown currency code **422s the entire batch**
  (``{"status":422,"message":"invalid currency: ZZZ"}``), so screen requested
  quotes against :func:`list_currencies` before asking for them.
* ``?scope=all`` on ``/v2/currencies`` adds retired currencies (205 vs 165).
  Without it, BGN, HRK, SLL and ZWL are absent and their history is
  unreachable -- which matters, because the corpus starts in 2013 and all
  four were live for part of it.
* Rates are daily-dense, including weekends and holidays.
* One range request returns a whole multi-year series: 147 quotes x 1 year is
  ~44k records in ~9 seconds.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterable

import pandas as pd

logger = logging.getLogger(__name__)

BASE_URL = "https://api.frankfurter.dev/v2"

# The default urllib UA is rejected with 403.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_TIMEOUT = 60
_MAX_RETRIES = 4


def _get(path: str, params: dict[str, str] | None = None):
    url = f"{BASE_URL}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # 422 means we asked for something that does not exist. Retrying
            # cannot fix that, and the message names the offending code.
            if exc.code == 422:
                raise ValueError(f"Frankfurter rejected the request: {exc.read()!r}")
            last_error = exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
        if attempt < _MAX_RETRIES - 1:
            time.sleep(2**attempt)
    raise RuntimeError(f"Frankfurter request failed after retries: {url}") from last_error


def list_currencies(scope_all: bool = True) -> pd.DataFrame:
    """Return the currencies v2 serves, with their coverage windows.

    ``scope_all=True`` includes retired currencies (BGN, HRK, SLL, ZWL ...),
    which the corpus needs because it reaches back to 2013.

    Columns: ``iso_code, name, start_date, end_date``.
    """
    params = {"scope": "all"} if scope_all else None
    payload = _get("/currencies", params)
    frame = pd.DataFrame(payload)
    frame["start_date"] = pd.to_datetime(frame["start_date"], errors="coerce")
    frame["end_date"] = pd.to_datetime(frame["end_date"], errors="coerce")
    return frame[["iso_code", "name", "start_date", "end_date"]]


def supported_codes(scope_all: bool = True) -> set[str]:
    """The set of codes safe to put in a ``quotes=`` list."""
    return set(list_currencies(scope_all=scope_all)["iso_code"])


def screen_quotes(
    requested: Iterable[str], supported: set[str] | None = None
) -> tuple[list[str], list[str]]:
    """Split ``requested`` into (accepted, rejected) against what v2 serves.

    This is not politeness -- one unknown code 422s the whole batch, so an
    unscreened request loses every currency, not just the bad one.
    """
    if supported is None:
        supported = supported_codes()
    accepted, rejected = [], []
    for code in dict.fromkeys(str(c).strip().upper() for c in requested):
        (accepted if code in supported else rejected).append(code)
    return accepted, rejected


def fetch_rates(
    quotes: Iterable[str],
    start: str,
    end: str,
    base: str = "USD",
    chunk_years: int = 2,
) -> pd.DataFrame:
    """Fetch ``base``->``quote`` rates over ``[start, end]``.

    Returns ``currency, date, rate_usd_to_local`` where the rate is units of
    quote per one unit of ``base``. ``quotes`` must already be screened.

    The range is split into ``chunk_years`` slices purely to keep any single
    response and any single retry bounded; the API itself will happily return
    a whole decade at once.
    """
    quote_list = [str(q).strip().upper() for q in quotes if str(q).strip()]
    quote_list = [q for q in dict.fromkeys(quote_list) if q != base]
    if not quote_list:
        return pd.DataFrame(columns=["currency", "date", "rate_usd_to_local"])

    start_ts = pd.Timestamp(start).normalize()
    end_ts = pd.Timestamp(end).normalize()

    records: list[dict] = []
    window_start = start_ts
    while window_start <= end_ts:
        window_end = min(
            window_start + pd.DateOffset(years=chunk_years) - pd.Timedelta(days=1),
            end_ts,
        )
        payload = _get(
            "/rates",
            {
                "from": window_start.strftime("%Y-%m-%d"),
                "to": window_end.strftime("%Y-%m-%d"),
                "base": base,
                "quotes": ",".join(quote_list),
            },
        )
        logger.info(
            "Frankfurter v2: %s..%s -> %s records",
            window_start.date(),
            window_end.date(),
            len(payload),
        )
        records.extend(payload)
        window_start = window_end + pd.Timedelta(days=1)

    if not records:
        return pd.DataFrame(columns=["currency", "date", "rate_usd_to_local"])

    frame = pd.DataFrame(records)
    frame = frame.rename(columns={"quote": "currency", "rate": "rate_usd_to_local"})
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["rate_usd_to_local"] = pd.to_numeric(
        frame["rate_usd_to_local"], errors="coerce"
    )
    frame = frame.dropna(subset=["currency", "date", "rate_usd_to_local"])
    # The API can return the day before `from` as a carry-in observation.
    frame = frame[(frame["date"] >= start_ts) & (frame["date"] <= end_ts)]
    frame = frame.drop_duplicates(subset=["currency", "date"], keep="last")
    return frame[["currency", "date", "rate_usd_to_local"]].reset_index(drop=True)
