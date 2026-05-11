"""Canonical wrapper for TheFuelPrice in Qatar."""

from fuel.fetchers._shared.menaap.thefuelprice import fetch_tfp_qa

fetch_tfp_qa.__module__ = __name__

__all__ = ["fetch_tfp_qa"]
