"""Côte d'Ivoire OCPV Info Prix — daily retail food-crop prices by market.

The **Office d'aide à la Commercialisation des Produits Vivriers (OCPV)**,
under the Ministère du Commerce, runs `infoprixocpv.com`, the national
food-crop price information platform. Three tables are published:

    /tableauprix          "bord champ"  (farmgate)
    /tableauprix_gros     wholesale
    /tableauprix_details  RETAIL   <- what this fetcher reads

Retail is the layer a consumer basket needs, so only that one is emitted.
The other two are legitimate future sources with a different
`analytical_role`/interpretation and would need their own manifests.

Columns: Marché | Produit | Prix Mini | Prix Moyen | Prix Maxi, in XOF.
`Prix Moyen` is emitted as `price_local`; min/max are recorded in `notes`
so the dispersion is not silently thrown away.

Coverage is genuinely broad and genuinely local: ~100 distinct products
across Ivorian markets (Abengourou, Aboisso, Bouaké, Minignan, ... Grand
Marchés) covering exactly the fresh-produce and staple leaves that
supermarket spiders structurally miss — plantain (afoto/agninnin, green /
ripe / alloco), yam (bêtê-bêtê, kponan, klinglè, assawa, boukari,
Florido), cassava, attiéké, gari, fonio, millet, maize, groundnut,
aubergine (gnangnan / klômgbo / N'drowa), okra, chilli, palm oil and palm
nuts, shea nut, kola nut, cashew, eggs, beef with and without bone, and a
long frozen-fish list (chinchard, maquereau, sardine, thon rouge, carpe
noire).

ACCESS (probed live 2026-09-05 — plain HTTP, no WAF, no auth, no CSRF):

    GET /tableauprix_details?dateDebut=YYYY-MM-DD&dateFin=YYYY-MM-DD&page=N

  * The GET filter form exposes `produitId`, `decoupageId`, `dateDebut`,
    `dateFin`, `prixMin`, `prixMax`. Only the two dates are used here.
  * Laravel pagination, **10 rows per page**.
  * TRAP: when a date filter is applied the page-number LINKS are not
    rendered at all, so the last page cannot be read off the markup. But
    `&page=N` still works. Pagination therefore walks until the response
    contains the site's own empty-state marker `listeempty`, rather than
    trusting a page-link count. Verified on 2026-09-03: pages 1, 2 and 3
    each returned 10 distinct rows although no page links were shown.
  * Unfiltered, the table reports 130 page links (~1,300 rows), which is
    the whole live board rather than one day.

DATE SEMANTICS: the table itself carries no date column — the date lives
only in the query. Each row is therefore stamped with the day it was
requested for, `period_kind: daily_avg`. Markets do not all report every
day (2026-09-04 and 2026-09-05 were empty, 2026-09-02/03 were not), which
is normal for this kind of board, not a fetch failure.

BACKFILL: the archive goes back years — 2025-06-10 and 2026-01-15 both
return data. The fetcher walks every day from `cutoff+1` to today, capped
by `_MAX_DAYS` per run so a 1970 `fallback_date` cannot turn the first run
into a multi-year crawl. Run it repeatedly to walk further back/forward;
the cutoff advances from the CSV each time.

UNIT: OCPV does not state the measurement unit anywhere in the table
markup. `unit` is left NULL rather than assuming "kg" — an invented unit
would silently corrupt any per-kg normalisation downstream.

coicop_classification: classifier — ~100 free-text local produce names
(including Ivorian varietal names like "Igname bêtê-bêtê" and "Aubergine
gnangnan") are exactly the long free-text list the ML classifier exists
for, and hand-mapping them would be guesswork. Same shape as
`insd_avg_prices` (Burkina Faso).
"""

from __future__ import annotations

import io
import logging
from datetime import date, timedelta

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Cote d'Ivoire"
_SOURCE_KEY = "ocpv_infoprix_civ"
_BASE = "https://infoprixocpv.com/tableauprix_details"
_IDENT = ["source_key", "observation_date", "item_name", "subnational_area"]

_EMPTY_MARKER = "listeempty"
# A busy day tops out between page 60 and 80 (measured on 2026-08-05: page 60
# still returned rows, page 80 was `listeempty`), so 150 is comfortable
# headroom. An earlier cap of 60 silently truncated busy days at exactly 600
# rows -- the flat-cap failure signature -- so a day that reaches the cap now
# logs a warning instead of passing quietly.
_MAX_PAGES_PER_DAY = 150
_MAX_DAYS = 45  # per-run backfill cap

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

_EXPECTED_COLS = {"Marche", "Produit", "Prix Mini", "Prix Moyen", "Prix Maxi"}


def _page(session, day: date, page: int) -> pd.DataFrame | None:
    """Return one page of the retail table, or None when the day is exhausted."""
    url = (
        f"{_BASE}?dateDebut={day.isoformat()}&dateFin={day.isoformat()}&page={page}"
    )
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    if _EMPTY_MARKER in resp.text:
        return None
    try:
        tables = pd.read_html(io.StringIO(resp.text))
    except ValueError:
        return None
    if not tables:
        return None
    df = tables[0]
    if not _EXPECTED_COLS.issubset(set(df.columns)):
        logger.warning(
            "[%s] unexpected columns %s on %s p%d -- layout changed",
            _SOURCE_KEY,
            list(df.columns),
            day,
            page,
        )
        return None
    return df


def _num(value) -> float | None:
    try:
        out = float(str(value).replace(" ", "").replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return None
    return out


def fetch_ocpv_infoprix_civ(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    start = max(cutoff + timedelta(days=1), today - timedelta(days=_MAX_DAYS - 1))
    if start > today:
        logger.info("[%s] nothing newer than cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    session = get_session()
    session.headers.update(_BROWSER_HEADERS)

    ts = get_scrape_ts()
    rows: list[dict] = []
    days_with_data = 0

    day = start
    while day <= today:
        page = 1
        day_rows = 0
        while page <= _MAX_PAGES_PER_DAY:
            try:
                df = _page(session, day, page)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[%s] %s p%d failed: %s", _SOURCE_KEY, day, page, exc)
                break
            if df is None or df.empty:
                break
            for _, rec in df.iterrows():
                market = str(rec["Marche"]).strip()
                item = str(rec["Produit"]).strip()
                mean = _num(rec["Prix Moyen"])
                lo = _num(rec["Prix Mini"])
                hi = _num(rec["Prix Maxi"])
                if not market or not item or mean is None or mean <= 0:
                    continue
                row = {
                    "observation_date": day.isoformat(),
                    "period_kind": "daily_avg",
                    "country": _COUNTRY,
                    "subnational_area": market,
                    "source_key": _SOURCE_KEY,
                    "coicop_code": None,
                    "item_name": item,
                    "price_local": mean,
                    "currency": "XOF",
                    "unit": None,
                    "source_url": (
                        f"{_BASE}?dateDebut={day.isoformat()}&dateFin={day.isoformat()}"
                    ),
                    "notes": (
                        "OCPV retail (prix au détail) market board; "
                        f"min={lo} max={hi} XOF; unit not stated by the source"
                    ),
                    "scrape_ts": ts,
                    "observation_hash": None,
                }
                row["observation_hash"] = make_hash(row, _IDENT)
                rows.append(row)
                day_rows += 1
            page += 1
        if page > _MAX_PAGES_PER_DAY:
            logger.warning(
                "[%s] %s hit the %d-page cap (%d rows) -- the day is TRUNCATED",
                _SOURCE_KEY,
                day,
                _MAX_PAGES_PER_DAY,
                day_rows,
            )
        if day_rows:
            days_with_data += 1
            logger.info("[%s] %s -> %d rows", _SOURCE_KEY, day, day_rows)
        day += timedelta(days=1)

    if not rows:
        logger.info(
            "[%s] no rows for %s..%s (markets do not report every day)",
            _SOURCE_KEY,
            start,
            today,
        )
        return None

    logger.info(
        "[%s] %d rows over %d reporting days (%s..%s, cutoff=%s)",
        _SOURCE_KEY,
        len(rows),
        days_with_data,
        start,
        today,
        cutoff,
    )
    return pd.DataFrame(rows)
