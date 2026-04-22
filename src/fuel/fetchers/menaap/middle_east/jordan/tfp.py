"""Canonical wrapper for TheFuelPrice in Jordan."""

from fuel.fetchers._shared.menaap.thefuelprice import fetch_tfp_jo

fetch_tfp_jo.__module__ = __name__

__all__ = ["fetch_tfp_jo"]
