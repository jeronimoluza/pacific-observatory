"""Canonical wrapper for TheFuelPrice in Saudi Arabia."""

from fuel.fetchers._shared.menaap.thefuelprice import fetch_tfp_sa

fetch_tfp_sa.__module__ = __name__

__all__ = ["fetch_tfp_sa"]
