"""Per-region seen-URL ledger, so collect can run without the archive disk.

One SQLite file per region (``~/text_state/<region>.sqlite``, override with
``TEXT_STATE_DIR``). Each row is one source, keyed ``<subregion>/<country>/<source>``
like its folder under ``data/text/<region>/``, and holds what collect would
otherwise read from that folder: the news.csv URL set and the urls.csv URLs
not in it (zlib-compressed, newline-joined; storing urls.csv whole would repeat
news.csv), the discovered-but-unscraped urls.csv rows, the failed_urls_seen.csv
file (compressed), and the newest news.csv date (the watermark).

The Mac copy is the master: ``po text merge`` updates it after appending a
staging run to the archive, and it is copied to the collect host afterwards.
"""

from __future__ import annotations

import io
import os
import sqlite3
import zlib
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd

STATE_DIR = Path(os.environ.get("TEXT_STATE_DIR", Path.home() / "text_state"))
URL_COLUMNS = ["url", "title", "date"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    key TEXT PRIMARY KEY,
    urls_only BLOB NOT NULL,
    news BLOB NOT NULL,
    pending BLOB NOT NULL,
    failed BLOB,
    watermark TEXT,
    n_urls INTEGER NOT NULL,
    n_news INTEGER NOT NULL,
    updated TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS blocked (
    key TEXT PRIMARY KEY,
    error TEXT NOT NULL,
    updated TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


@dataclass
class SourceState:
    urls: set[str]
    news: set[str]
    pending: pd.DataFrame  # urls.csv rows (url, title, date) not in news.csv
    failed: Optional[bytes]  # raw failed_urls_seen.csv, None if absent
    watermark: Optional[str]  # newest news.csv date, YYYY-MM-DD


def _pack(urls: set[str]) -> bytes:
    return zlib.compress("\n".join(sorted(urls)).encode("utf-8"))


def _unpack(blob: bytes) -> set[str]:
    text = zlib.decompress(blob).decode("utf-8")
    return set(text.split("\n")) if text else set()


def _pack_frame(df: pd.DataFrame) -> bytes:
    return zlib.compress(df[URL_COLUMNS].to_csv(index=False).encode("utf-8"))


def _unpack_frame(blob: bytes) -> pd.DataFrame:
    return pd.read_csv(
        io.BytesIO(zlib.decompress(blob)), dtype=str, keep_default_na=False
    )


def newest_date(dates: pd.Series) -> Optional[str]:
    """Newest YYYY-MM-DD in ``dates``, ignoring unparseable and future values."""
    parsed = pd.to_datetime(
        dates.astype(str).str[:10], format="%Y-%m-%d", errors="coerce"
    )
    parsed = parsed[parsed <= pd.Timestamp(date.today() + timedelta(days=1))]
    return (
        None
        if parsed.empty or pd.isna(parsed.max())
        else parsed.max().strftime("%Y-%m-%d")
    )


class Ledger:
    def __init__(self, region: str, state_dir: Path = STATE_DIR):
        state_dir.mkdir(parents=True, exist_ok=True)
        self.path = state_dir / f"{region}.sqlite"
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(_SCHEMA)

    def get(self, key: str) -> Optional[SourceState]:
        row = self.conn.execute(
            "SELECT urls_only, news, pending, failed, watermark FROM sources "
            "WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        urls_only, news, pending, failed, watermark = row
        news = _unpack(news)
        return SourceState(
            _unpack(urls_only) | news,
            news,
            _unpack_frame(pending),
            zlib.decompress(failed) if failed is not None else None,
            watermark,
        )

    def put(self, key: str, state: SourceState) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO sources "
            "(key, urls_only, news, pending, failed, watermark, n_urls, n_news) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                key,
                _pack(state.urls - state.news),
                _pack(state.news),
                _pack_frame(state.pending),
                zlib.compress(state.failed) if state.failed is not None else None,
                state.watermark,
                len(state.urls),
                len(state.news),
            ),
        )
        self.conn.commit()

    def keys(self) -> list[str]:
        return [k for (k,) in self.conn.execute("SELECT key FROM sources ORDER BY key")]

    def block(self, key: str, error: str) -> None:
        """Mark a source whose archive files could not be read; collect skips it."""
        self.conn.execute("DELETE FROM sources WHERE key = ?", (key,))
        self.conn.execute(
            "INSERT OR REPLACE INTO blocked (key, error) VALUES (?, ?)", (key, error)
        )
        self.conn.commit()

    def blocked(self, key: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT error FROM blocked WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    def close(self) -> None:
        self.conn.close()


def read_source_dir(source_dir: Path) -> SourceState:
    """Build a source's ledger state from its archive folder."""
    urls_csv = source_dir / "urls.csv"
    news_csv = source_dir / "news.csv"
    failed_csv = source_dir / "failed_urls_seen.csv"

    url_rows = (
        pd.read_csv(urls_csv, usecols=URL_COLUMNS, dtype=str, keep_default_na=False)
        if urls_csv.exists()
        else pd.DataFrame(columns=URL_COLUMNS)
    )
    news: set[str] = set()
    newest: list[str] = []
    if news_csv.exists():
        for chunk in pd.read_csv(
            news_csv, usecols=["url", "date"], dtype=str, chunksize=500_000
        ):
            news.update(chunk["url"].dropna().astype(str))
            top = newest_date(chunk["date"].dropna())
            if top:
                newest.append(top)
    urls = set(url_rows["url"].astype(str))
    return SourceState(
        urls=urls,
        news=news,
        pending=url_rows[~url_rows["url"].isin(news)].drop_duplicates("url"),
        failed=failed_csv.read_bytes() if failed_csv.exists() else None,
        watermark=max(newest) if newest else None,
    )


def iter_source_dirs(region_dir: Path) -> Iterator[tuple[str, Path]]:
    """Yield (key, dir) for every <subregion>/<country>/<source> folder."""
    for source_dir in sorted(region_dir.glob("*/*/*")):
        if source_dir.is_dir() and not source_dir.name.startswith((".", "_")):
            yield str(source_dir.relative_to(region_dir)), source_dir


def bootstrap(
    region: str, data_base: Path, state_dir: Path = STATE_DIR
) -> tuple[int, dict[str, str]]:
    """Read every source folder of ``region`` into its ledger.

    A source whose files do not parse is recorded as blocked (and staged collect
    skips it) instead of aborting the region. Returns (sources written, blocked).
    """
    ledger = Ledger(region, state_dir)
    n, blocked = 0, {}
    try:
        for key, source_dir in iter_source_dirs(data_base / region):
            if (
                not (source_dir / "news.csv").exists()
                and not (source_dir / "urls.csv").exists()
            ):
                continue
            try:
                state = read_source_dir(source_dir)
            except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as e:
                blocked[key] = f"{type(e).__name__}: {e}"
                ledger.block(key, blocked[key])
                print(f"  BLOCKED {key}: {blocked[key]}", flush=True)
                continue
            ledger.put(key, state)
            ledger.conn.execute("DELETE FROM blocked WHERE key = ?", (key,))
            ledger.conn.commit()
            n += 1
            print(f"  {key}", flush=True)
    finally:
        ledger.close()
    return n, blocked
