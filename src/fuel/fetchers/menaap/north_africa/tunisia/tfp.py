"""Canonical wrapper for TheFuelPrice in Tunisia."""

from fuel.fetchers._shared.menaap.thefuelprice import fetch_tfp_tn

fetch_tfp_tn.__module__ = __name__

__all__ = ["fetch_tfp_tn"]
