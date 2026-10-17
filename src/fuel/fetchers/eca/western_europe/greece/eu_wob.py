"""Canonical wrapper for the EU Weekly Oil Bulletin in Greece."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_gr

fetch_eu_wob_gr.__module__ = __name__

__all__ = ["fetch_eu_wob_gr"]
