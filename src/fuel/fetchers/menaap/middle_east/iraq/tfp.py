"""Canonical wrapper for TheFuelPrice in Iraq."""

from fuel.fetchers._shared.menaap.thefuelprice import fetch_tfp_iq

fetch_tfp_iq.__module__ = __name__

__all__ = ["fetch_tfp_iq"]
