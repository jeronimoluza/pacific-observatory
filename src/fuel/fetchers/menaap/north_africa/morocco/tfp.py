"""Canonical wrapper for TheFuelPrice in Morocco."""

from fuel.fetchers._shared.menaap.thefuelprice import fetch_tfp_ma

fetch_tfp_ma.__module__ = __name__

__all__ = ["fetch_tfp_ma"]
