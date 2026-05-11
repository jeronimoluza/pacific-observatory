"""Canonical wrapper for TheFuelPrice in Kuwait."""

from fuel.fetchers._shared.menaap.thefuelprice import fetch_tfp_kw

fetch_tfp_kw.__module__ = __name__

__all__ = ["fetch_tfp_kw"]
