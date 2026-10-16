"""Enabled text sources, their Google News editions, and what the ledger says we collected.

The ledger (``<TEXT_STATE_DIR>/<region>.sqlite``) keeps each source's collected
URLs (``news``) without dates; only the newest date (``watermark``) is stored.
So a week's count comes from one of two places:
- ``url_date``: URLs whose path carries a date in the week, used when at least
  DATED_MIN of the source's collected URLs carry one;
- ``ledger_delta``: ``n_news`` now minus ``n_news`` in the previous report, when
  the ledger row was updated in between (counts what was collected between the
  two runs, not what was published in the week).
"""

from __future__ import annotations

import csv
import re
import sqlite3
import zlib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import yaml

from core.config import discover_pipeline_configs, parse_config_path
from text.analysis.utils import LANGUAGE_ALIASES
from text.collect import CONFIGS_DIR, _split_disabled
from text.ledger import STATE_DIR

REPO = Path(__file__).resolve().parents[3]
DATED_MIN = 0.5

# config `language` -> Google `hl`. Short codes pass through; long names come from
# the inverted LANGUAGE_ALIASES plus the names it does not list.
_HL = {v: k for k, v in LANGUAGE_ALIASES.items()} | {
    "zh": "zh-CN",
    "chinese_simplified": "zh-CN",
    "chinese_traditional": "zh-TW",
    "hindi": "hi",
    "urdu": "ur",
    "tamil": "ta",
    "somali": "so",
    "swahili": "sw",
    "lao": "lo",
    "amharic": "am",
    "me": "sr",
    "pap": "nl",
    "filipino": "en",
    "tok_pisin": "en",
    "tetum": "pt",
    "tet": "pt",
}
# Native edition tried last: some configs tag local-language sites `en`.
NATIVE = {
    "BD": "bn", "IN": "hi", "NP": "ne", "LK": "si", "PK": "ur", "AF": "fa",
    "ET": "am", "LA": "lo", "KH": "km", "MM": "my", "TH": "th", "MN": "mn",
    "CN": "zh-CN", "TW": "zh-TW", "HK": "zh-HK", "TM": "ru", "TJ": "ru",
    "KG": "ru", "UZ": "ru", "KZ": "ru", "BY": "ru", "AZ": "az", "SO": "so",
    "TZ": "sw", "KE": "sw", "IR": "fa", "IL": "he",
}  # fmt: skip
# countries.yaml has iso3 only; this table holds iso2 for 209 of its 216 slugs.
_ISO_CSV = REPO / "src/prices/rtcal/_data/country_context_metadata.csv"
_ISO2_EXTRA = {
    "FRO": "FO",
    "IMN": "IM",
    "MCO": "MC",
    "ERI": "ER",
    "STP": "ST",
    "SYC": "SC",
}
_DATE_RX = [
    re.compile(r"/(20\d\d)[/-](\d\d)[/-](\d\d)(?:/|-|$)"),
    re.compile(r"/(20\d\d)(\d\d)(\d\d)(?:/|-|_|\d)"),
    re.compile(r"/(20\d\d)/(\d\d)(\d\d)/"),
]


@dataclass
class Source:
    source: str
    region: str
    subregion: str
    country: str
    domain: str
    language: str
    gnews: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.subregion}/{self.country}/{self.source}"


def iso2_map() -> dict[str, str]:
    countries = yaml.safe_load((REPO / "src/configs/countries.yaml").read_text())
    with open(_ISO_CSV, newline="") as f:
        by3 = {r["country_iso3"]: r["country_iso2"] for r in csv.DictReader(f)}
    by3 |= _ISO2_EXTRA
    return {slug: by3.get((c or {}).get("iso3"), "") for slug, c in countries.items()}


def load_sources(region=None, countries=(), sources=()) -> list[Source]:
    configs = discover_pipeline_configs(CONFIGS_DIR, region=region)
    configs, _ = _split_disabled(configs)
    out = []
    for p in configs:
        rgn, sub, ctry = parse_config_path(p, CONFIGS_DIR)
        if (countries and ctry not in countries) or (sources and p.stem not in sources):
            continue
        cfg = yaml.safe_load(p.read_text()) or {}
        domain = urlparse(cfg.get("base_url") or "").netloc.lower().removeprefix("www.")
        if not domain:
            continue
        lang = str(cfg.get("language") or "en").strip("[]\"' ").lower()
        out.append(Source(p.stem, rgn, sub, ctry, domain, lang, cfg.get("gnews") or {}))
    return out


def editions(src: Source, iso2: dict[str, str]) -> list[tuple[str, str]]:
    """(hl, gl) pairs to try in order: config/override, en-US, native edition."""
    cc = src.gnews.get("gl") or iso2.get(src.country) or "US"
    hl = src.gnews.get("hl") or _HL.get(src.language, src.language)
    tries = [(hl, cc)]
    for alt in (("en", "US"), (NATIVE.get(cc), cc)):
        if alt[0] and alt not in tries:
            tries.append(alt)
    return tries


def url_date(url: str) -> date | None:
    path = urlparse(url).path
    for rx in _DATE_RX:
        m = rx.search(path)
        if m:
            try:
                return date(*map(int, m.groups()))
            except ValueError:
                return None
    return None


def norm_url(url: str) -> str:
    u = urlparse(url)
    return u.netloc.lower().removeprefix("www.") + u.path.rstrip("/")


class LedgerReader:
    """Read-only view of the region ledgers; never creates or writes one."""

    def __init__(self, state_dir: Path = STATE_DIR):
        self.state_dir = state_dir
        self._conns: dict[str, sqlite3.Connection | None] = {}

    def _conn(self, region: str):
        if region not in self._conns:
            path = self.state_dir / f"{region}.sqlite"
            self._conns[region] = (
                sqlite3.connect(f"file:{path}?mode=ro", uri=True)
                if path.exists()
                else None
            )
        return self._conns[region]

    def row(self, src: Source) -> dict | None:
        """{n_news, updated, urls (news+seen, normalized), news (raw)} or None."""
        conn = self._conn(src.region)
        if conn is None:
            return None
        hit = conn.execute(
            "SELECT news, urls_only, n_news, updated FROM sources WHERE key = ?",
            (src.key,),
        ).fetchone()
        if hit is None:
            return None
        news_b, only_b, n_news, updated = hit
        news = [
            u
            for u in zlib.decompress(news_b).decode("utf-8", "replace").split("\n")
            if u
        ]
        only = [
            u
            for u in zlib.decompress(only_b).decode("utf-8", "replace").split("\n")
            if u
        ]
        return dict(
            n_news=n_news,
            updated=updated,
            news=news,
            seen={norm_url(u) for u in news + only},
        )


def week_count_by_url_date(
    news: list[str], start: date, end: date
) -> tuple[int, float]:
    """(collected URLs dated in [start, end], share of collected URLs with a date)."""
    dates = [url_date(u) for u in news]
    dated = [d for d in dates if d]
    share = len(dated) / len(news) if news else 0.0
    return sum(start <= d <= end for d in dated), share
