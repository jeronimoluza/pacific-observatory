"""Canonical wrapper for TheFuelPrice in Algeria."""

from fuel.fetchers._shared.menaap.thefuelprice import fetch_tfp_dz

fetch_tfp_dz.__module__ = __name__

__all__ = ["fetch_tfp_dz"]
