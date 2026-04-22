"""Canonical wrapper for TheFuelPrice in Libya."""

from fuel.fetchers._shared.menaap.thefuelprice import fetch_tfp_ly

fetch_tfp_ly.__module__ = __name__

__all__ = ["fetch_tfp_ly"]
