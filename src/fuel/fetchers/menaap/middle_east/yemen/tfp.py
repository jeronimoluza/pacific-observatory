"""Canonical wrapper for TheFuelPrice in Yemen."""

from fuel.fetchers._shared.menaap.thefuelprice import fetch_tfp_ye

fetch_tfp_ye.__module__ = __name__

__all__ = ["fetch_tfp_ye"]
