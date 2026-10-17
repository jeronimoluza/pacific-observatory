"""Canonical wrapper for the EU Weekly Oil Bulletin in Germany."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_de

fetch_eu_wob_de.__module__ = __name__

__all__ = ["fetch_eu_wob_de"]
