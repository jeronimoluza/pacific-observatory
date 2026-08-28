"""One-off history backfill for the Xinfadi (新发地) wholesale fetcher.

The live fetcher walks a fixed 30-day lookback so routine `prices collect`
runs never trigger a multi-year pull. The source publishes back to
2022-01-01 (~760k rows), which this walks once, month by month.

Resumable: rows are keyed by the fetcher's own `observation_hash`, so a
re-run after an interruption re-fetches the window but appends nothing that
is already on disk. Rows are flushed per calendar year rather than per month
to keep the number of full-CSV rewrites small.

    python -m prices.tools.backfill_xinfadi [--start 2022-01-01] [--pause 0.5]
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import click
import pandas as pd

from prices.collect import _DATA_ROOT
from prices.fetchers.eap.east_asia.china.xinfadi_wholesale import collect_window
from prices.fetchers.utils import get_scrape_ts, get_session
from prices.writers import PRICE_COLUMNS, append_observations, output_path_for

logger = logging.getLogger(__name__)

_HISTORY_START = date(2022, 1, 1)


def _month_windows(start: date, end: date):
    cur = start
    while cur <= end:
        nxt = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
        yield cur, min(nxt - timedelta(days=1), end)
        cur = nxt


@click.command()
@click.option("--start", default=_HISTORY_START.isoformat(), help="First date to pull.")
@click.option("--pause", default=0.5, help="Seconds to sleep between API pages.")
def main(start: str, pause: float) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    out_path = output_path_for(
        data_root=_DATA_ROOT,
        region="eap",
        subregion="east_asia",
        country="china",
        source="xinfadi_wholesale",
        analytical_role="official_avg",
    )
    session = get_session()
    ts = get_scrape_ts()
    begin = date.fromisoformat(start)
    today = date.today()

    batch: list[dict] = []
    batch_year = begin.year
    appended = 0

    def flush(year: int) -> None:
        nonlocal batch, appended
        if not batch:
            return
        n = append_observations(pd.DataFrame(batch), out_path, columns=PRICE_COLUMNS)
        appended += n
        logger.info(
            "[%d] flushed %d fetched → %d new (running total %d)",
            year,
            len(batch),
            n,
            appended,
        )
        batch = []

    for w_start, w_end in _month_windows(begin, today):
        if w_start.year != batch_year:
            flush(batch_year)
            batch_year = w_start.year
        rows = collect_window(session, ts, w_start, w_end, date.min, pause=pause)
        logger.info("%s..%s → %d rows", w_start, w_end, len(rows))
        batch.extend(rows)
    flush(batch_year)

    logger.info("Backfill done: %d new rows appended → %s", appended, out_path)


if __name__ == "__main__":
    main()
