"""Canonical wrapper for the EU Weekly Oil Bulletin in Bulgaria."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_bg

fetch_eu_wob_bg.__module__ = __name__

__all__ = ["fetch_eu_wob_bg"]
