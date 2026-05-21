"""Shared helpers for prices fetchers — use when convenient, not mandatory."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

_HASH_SEP = b"\x00"


def get_scrape_ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_hash(row: dict, identifying_fields: list[str]) -> str:
    """SHA-1 over a fixed identifying tuple, NULL-separated to avoid collisions."""
    parts = [str(row.get(f, "")) for f in identifying_fields]
    return hashlib.sha1(_HASH_SEP.join(p.encode("utf-8") for p in parts)).hexdigest()


def get_session(retries: int = 3, backoff: float = 0.5) -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": "pacific-observatory/prices (+research)"})
    return s


def safe_last_date(df: pd.DataFrame, col: str = "observation_date"):
    if df is None or df.empty:
        return None
    return pd.to_datetime(df[col]).max().date()
