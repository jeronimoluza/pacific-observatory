"""Emit visually verified Palau Pacific Resort in-room dining prices."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


SOURCE_KEY = "palau_pacific_resort_dining"
FIXTURE_PATH = Path(__file__).with_name("palau_pacific_resort_dining_fixture.json")
IDENTITY_FIELDS = ("source_key", "observation_date", "item_name", "unit")


def _observation_hash(row: dict) -> str:
    identity = "\x1f".join(str(row[field]) for field in IDENTITY_FIELDS)
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def parse_verified_menu_fixture(payload: dict) -> list[dict]:
    """Validate and transform the curated image-PDF transcription."""
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("fixture must contain an items list")
    if payload.get("source_key") != SOURCE_KEY:
        raise ValueError("fixture source_key does not match the fetcher")
    if payload.get("currency") != "USD":
        raise ValueError("fixture currency must be USD")

    source_url = str(payload.get("source_url") or "").strip()
    observation_date = str(payload.get("observation_date") or "").strip()
    scrape_ts = str(payload.get("captured_at_utc") or "").strip()
    if not source_url.startswith("https://www.palauppr.com/"):
        raise ValueError("fixture must retain the first-party source URL")
    try:
        date.fromisoformat(observation_date)
    except ValueError as exc:
        raise ValueError("fixture observation_date must be ISO formatted") from exc
    if not scrape_ts:
        raise ValueError("fixture must retain its capture timestamp")

    rows = []
    seen_ids = set()
    seen_names = set()
    for item in payload["items"]:
        if not isinstance(item, dict):
            raise ValueError("every fixture item must be an object")
        item_id = str(item.get("item_id") or "").strip()
        name = " ".join(str(item.get("name") or "").split())
        category = " ".join(str(item.get("category") or "").split())
        try:
            page = int(item.get("page"))
            price = Decimal(str(item.get("price")))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"invalid page or price for {item_id or name!r}") from exc
        if not item_id or not name or not category:
            raise ValueError("item_id, name, and category are required")
        if page not in {1, 2, 3, 4} or price <= 0 or price.as_tuple().exponent < -2:
            raise ValueError(f"invalid page or USD price for {item_id!r}")
        if item_id in seen_ids or name.casefold() in seen_names:
            raise ValueError(f"duplicate fixture item {item_id!r}")
        seen_ids.add(item_id)
        seen_names.add(name.casefold())

        row = {
            "observation_date": observation_date,
            "period_kind": "snapshot",
            "country": "Palau",
            "subnational_area": "Koror",
            "source_key": SOURCE_KEY,
            "coicop_code": "11.1.1",
            "item_name": name,
            "price_local": float(price),
            "currency": "USD",
            "unit": "menu item",
            "source_url": f"{source_url}#page={page}",
            "source_page": page,
            "notes": (
                f"{category}; visually verified on menu page {page}; "
                "price includes service charge and PGST"
            ),
            "scrape_ts": scrape_ts,
            "observation_hash": None,
        }
        row["observation_hash"] = _observation_hash(row)
        rows.append(row)
    return rows


def load_verified_menu_fixture(path: Path = FIXTURE_PATH) -> list[dict]:
    return parse_verified_menu_fixture(json.loads(path.read_text(encoding="utf-8")))


def fetch_palau_pacific_resort_dining(cutoff: date):
    """Return the saved menu snapshot when it is newer than the cutoff."""
    rows = [
        row
        for row in load_verified_menu_fixture()
        if date.fromisoformat(row["observation_date"]) > cutoff
    ]
    if not rows:
        return None
    import pandas as pd

    return pd.DataFrame(rows)
