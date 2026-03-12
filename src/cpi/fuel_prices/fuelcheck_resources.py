"""Resource discovery helpers for NSW FuelCheck backfills."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

import pandas as pd

from .utils import get_session

DATASET_URL = "https://data.nsw.gov.au/data/dataset/fuel-check"
PACKAGE_URL = (
    "https://data.nsw.gov.au/data/api/3/action/package_show"
    "?id=a97a46fc-2bdd-4b90-ac7f-0cb1e8d7ac3b"
)

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


@dataclass(frozen=True)
class Resource:
    id: str
    name: str
    url: str
    fmt: str
    last_modified: str | None
    year: int | None
    month: int | None


def _extract_period(text: str) -> tuple[int, int] | None:
    s = (text or "").lower()

    m = re.search(
        r"\b(?P<mon>jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)"
        r"[\s_\-]*?(?P<year>20\d{2})\b",
        s,
    )
    if m:
        return int(m.group("year")), MONTHS[m.group("mon")]

    m = re.search(
        r"\b(?P<mon>january|february|march|april|may|june|july|august|september|october|november|december)"
        r"[\s_\-]*?(?P<year>20\d{2})\b",
        s,
    )
    if m:
        return int(m.group("year")), MONTHS[m.group("mon")]

    return None


def _resource_format(resource: dict) -> str:
    fmt = str(resource.get("format") or "").strip().lower()
    if fmt:
        if "csv" in fmt:
            return "csv"
        if "xlsx" in fmt:
            return "xlsx"
        if re.search(r"\bxls\b", fmt) or fmt.endswith(".xls"):
            return "xls"
        return fmt

    url = str(resource.get("url") or "")
    if "." not in url:
        return ""
    return url.split("?")[0].rsplit(".", 1)[-1].lower()


def _is_price_history_resource(resource: dict) -> bool:
    text = f"{resource.get('name', '')} {resource.get('url', '')}".lower()
    return "price history" in text or "price_history" in text or "pricehistory" in text


def load_package_resources() -> list[Resource]:
    """Load candidate FuelCheck resources from the CKAN package API."""
    session = get_session()
    resp = session.get(PACKAGE_URL, timeout=45)
    resp.raise_for_status()
    payload = resp.json()
    result = payload.get("result") if isinstance(payload, dict) else None
    resources = result.get("resources", []) if isinstance(result, dict) else []

    out: list[Resource] = []
    for resource in resources:
        fmt = _resource_format(resource)
        if fmt not in {"csv", "xlsx", "xls"}:
            continue
        if not _is_price_history_resource(resource):
            continue

        rid = (
            str(resource.get("id") or "").strip()
            or str(resource.get("url") or "").strip()
        )
        name = str(resource.get("name") or "").strip()
        url = str(resource.get("url") or "").strip()
        if not url:
            continue

        period = _extract_period(f"{name} {url}")
        year, month = period if period else (None, None)
        out.append(
            Resource(
                id=rid,
                name=name,
                url=url,
                fmt=fmt,
                last_modified=(
                    resource.get("last_modified") or resource.get("metadata_modified")
                ),
                year=year,
                month=month,
            )
        )
    return out


def pick_best_resources_per_period(resources: list[Resource]) -> list[Resource]:
    """Pick the best resource per month, preferring CSV and newer revisions."""
    by_period: dict[tuple[int, int], list[Resource]] = {}
    no_period: list[Resource] = []
    for resource in resources:
        if resource.year and resource.month:
            by_period.setdefault((resource.year, resource.month), []).append(resource)
        else:
            no_period.append(resource)

    fmt_rank = {"csv": 0, "xlsx": 1, "xls": 2}

    selected: list[Resource] = []
    for items in by_period.values():
        items_sorted = sorted(
            items,
            key=lambda item: (
                fmt_rank.get(item.fmt, 9),
                str(item.last_modified or ""),
            ),
        )
        selected.append(items_sorted[0])

    selected.extend(sorted(no_period, key=lambda item: str(item.last_modified or "")))
    selected.sort(key=lambda item: (item.year or 9999, item.month or 99, item.name))
    return selected


def parse_resource_bytes(content: bytes, fmt: str) -> pd.DataFrame:
    """Parse raw FuelCheck bytes into a dataframe."""
    if fmt == "csv":
        bio = io.BytesIO(content)
        try:
            return pd.read_csv(bio, low_memory=False)
        except UnicodeDecodeError:
            bio.seek(0)
            return pd.read_csv(bio, low_memory=False, encoding="latin-1")
    return pd.read_excel(io.BytesIO(content))
