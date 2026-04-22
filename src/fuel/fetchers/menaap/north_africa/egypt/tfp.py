"""Canonical wrapper for TheFuelPrice in Egypt."""

from fuel.fetchers._shared.menaap.thefuelprice import fetch_tfp_eg

fetch_tfp_eg.__module__ = __name__

__all__ = ["fetch_tfp_eg"]
