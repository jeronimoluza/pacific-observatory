"""Publish commands for fuel_prices outputs."""

from __future__ import annotations

from pathlib import Path

from ..constants import DATA_DIR
from ..loader import load_fuel_data
from ..visualize import gen_fuel_html
from ..visualize_policy import gen_policy_html, load_policy_data


def _publish_prices(fuel_data: dict | None = None) -> Path:
    out = DATA_DIR / "fuel_prices.html"
    print(f"Generating fuel prices HTML -> {out}")
    if fuel_data is None:
        print("Loading fuel prices data...")
        fuel_data = load_fuel_data()
    gen_fuel_html(fuel_data, out)
    return out


def _publish_policy(fuel_data: dict | None = None) -> Path:
    out = DATA_DIR / "fuel_policy_overview.html"
    print(f"Generating fuel policy HTML -> {out}")
    if fuel_data is None:
        print("Loading fuel prices data...")
        fuel_data = load_fuel_data()
    print("Loading policy data...")
    policy_data = load_policy_data()
    gen_policy_html(policy_data, fuel_data, out)
    return out


def cmd_publish(args) -> None:
    """Regenerate fuel publish artifacts."""
    target = getattr(args, "target", "all")
    fuel_data = None

    if target in {"all", "prices", "policy"}:
        print("Loading fuel prices data...")
        fuel_data = load_fuel_data()

    if target in {"all", "prices"}:
        _publish_prices(fuel_data)
    if target in {"all", "policy"}:
        _publish_policy(fuel_data)

    print("Done.")
