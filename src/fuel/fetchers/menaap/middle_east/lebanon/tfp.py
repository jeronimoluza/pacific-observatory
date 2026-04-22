"""Canonical wrapper for TheFuelPrice in Lebanon."""

from fuel.fetchers._shared.menaap.thefuelprice import fetch_tfp_lb

fetch_tfp_lb.__module__ = __name__

__all__ = ["fetch_tfp_lb"]
