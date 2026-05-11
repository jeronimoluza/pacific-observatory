"""Canonical wrapper for TheFuelPrice in Bahrain."""

from fuel.fetchers._shared.menaap.thefuelprice import fetch_tfp_bh

fetch_tfp_bh.__module__ = __name__

__all__ = ["fetch_tfp_bh"]
