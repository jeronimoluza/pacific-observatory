"""Canonical wrapper for TheFuelPrice in Syria."""

from fuel.fetchers._shared.menaap.thefuelprice import fetch_tfp_sy

fetch_tfp_sy.__module__ = __name__

__all__ = ["fetch_tfp_sy"]
