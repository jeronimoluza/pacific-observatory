"""Canonical wrapper for TheFuelPrice in West Bank and Gaza."""

from fuel.fetchers._shared.menaap.thefuelprice import fetch_tfp_ps

fetch_tfp_ps.__module__ = __name__

__all__ = ["fetch_tfp_ps"]
