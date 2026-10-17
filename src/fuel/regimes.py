"""Fuel price-regime table: one row per iso3 x product x valid_from.

The table (``configs/_regimes/regimes.yaml``) is the single source for the
Tab 1 badge. A cell the table does not cover falls back to the WB CSV +
``regime_overrides`` path, and every fallback is logged.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from .reference.subsidies import TABLE_PRODUCTS, _apply_hardcoded_overrides

logger = logging.getLogger(__name__)

REGIMES_PATH = Path(__file__).resolve().parent / "configs" / "_regimes" / "regimes.yaml"

REGIMES = {"administered", "formula", "ceiling", "floor", "market", "dual"}
PROVENANCES = {"wb2024", "override", "audit_manual", "workbook_corpus", "watcher"}
CONFIDENCES = {"high", "medium", "low"}
COLUMNS = [
    "iso3",
    "product",
    "valid_from",
    "valid_to",
    "regime",
    "adjust_freq",
    "subsidy",
    "subsidy_note",
    "price_basis",
    "evidence_url",
    "evidence_sha256",
    "evidence_quote",
    "confidence",
    "provenance",
    "reviewer",
    "reviewed_at",
    "note",
    "temporary_until",
]

# Series whose source is not a retail pump price carry this label in the
# Excel and the dashboard (price_basis in the source YAML).
NOT_PUMP_PRICE = "Best available, not pump price"


def basis_note(price_basis) -> str:
    """``NOT_PUMP_PRICE`` unless every basis in a comma list is retail."""
    parts = {p.strip() for p in str(price_basis or "retail").split(",") if p.strip()}
    return "" if parts <= {"retail", "nan"} else NOT_PUMP_PRICE


def badge(regime: str) -> str:
    """Badge the dashboard shows: ``market`` is Market, ``floor`` is Reference
    Price (a regulated minimum, not a controlled pump price), the rest Price
    Control."""
    if regime == "market":
        return "Market"
    return "Reference Price" if regime == "floor" else "Price Control"


def load_regimes(path: Path = REGIMES_PATH) -> pd.DataFrame:
    """Read and validate the table; an empty valid_from sorts before any date."""
    with open(path, encoding="utf-8") as f:
        rows = (yaml.safe_load(f) or {}).get("regimes") or []
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["subsidy"] = df["subsidy"].eq(True)
    df["price_basis"] = df["price_basis"].fillna("retail")
    for col in ("valid_from", "valid_to", "temporary_until"):
        df[col] = pd.to_datetime(df[col], errors="raise")
    bad = df[
        ~df["regime"].isin(REGIMES)
        | ~df["product"].isin(TABLE_PRODUCTS)
        | ~df["provenance"].isin(PROVENANCES)
        | ~df["confidence"].isin(CONFIDENCES)
        | ~df["iso3"].astype(str).str.fullmatch(r"[A-Z]{3}")
    ]
    if not bad.empty:
        raise ValueError(f"{path}: invalid rows\n{bad[COLUMNS[:5]].to_string()}")
    dup = df.duplicated(["iso3", "product", "valid_from"], keep=False)
    if dup.any():
        raise ValueError(f"{path}: duplicate cells\n{df[dup][COLUMNS[:5]].to_string()}")
    return df


def regime_at(table: pd.DataFrame, iso3: str, product: str, on: date) -> dict | None:
    """The row in force for (iso3, product) on ``on``, or None."""
    ts = pd.Timestamp(on)
    rows = table[
        (table["iso3"] == iso3)
        & (table["product"] == product)
        & (table["valid_from"].isna() | (table["valid_from"] <= ts))
        & (table["valid_to"].isna() | (table["valid_to"] >= ts))
    ]
    if rows.empty:
        return None
    rows = rows.sort_values("valid_from", na_position="first")
    return rows.iloc[-1].to_dict()


def apply_regime_table(
    df_regime: pd.DataFrame,
    product_regimes: dict[str, dict[str, dict]],
    isos: set[str],
    notes: dict[str, dict[str, dict]],
    on: date | None = None,
    path: Path = REGIMES_PATH,
) -> tuple[pd.DataFrame, dict[str, dict[str, dict]]]:
    """Replace the badge cells of ``isos`` with the table rows in force on ``on``.

    ``on`` defaults to today (UTC). Cells without a table row keep the
    WB/override value (logged). Countries outside ``isos`` are untouched. The
    country-level regime is re-derived only for countries whose cells change,
    and a changed cell's popover (``notes``) cites the table row's evidence.
    """
    on = on or datetime.now(timezone.utc).date()
    if not path.exists():
        logger.warning("Regime table not found: %s; using WB + overrides", path)
        return df_regime, product_regimes
    table = load_regimes(path)
    changed: dict[str, dict[str, dict]] = {}
    for iso3 in sorted(isos):
        old = product_regimes.get(iso3, {})
        new: dict[str, dict] = {}
        for prod in TABLE_PRODUCTS:
            row = regime_at(table, iso3, prod, on)
            if row is None:
                if prod in old:
                    logger.info(
                        "Regime fallback %s %s -> %s (no table row)",
                        iso3,
                        prod,
                        old[prod].get("regime"),
                    )
                    new[prod] = old[prod]
                continue
            new[prod] = {
                "regime": badge(row["regime"]),
                "subsidy": bool(row["subsidy"]),
            }
            if new[prod] != old.get(prod) and isinstance(row["evidence_url"], str):
                label = f"{row['regime']} ({row['provenance']}, {row['confidence']} confidence)"
                cell = notes.setdefault(iso3, {}).setdefault(prod, {})
                cell["classification_sources"] = [
                    {"label": label, "url": row["evidence_url"]}
                ]
        if new != old:
            changed[iso3] = new
            product_regimes[iso3] = new
    if changed:
        df_regime, product_regimes = _apply_hardcoded_overrides(
            df_regime, product_regimes, changed
        )
    return df_regime, product_regimes
