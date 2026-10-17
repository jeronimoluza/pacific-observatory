"""Canonical wrapper for the EU Weekly Oil Bulletin in Ireland."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_ie

fetch_eu_wob_ie.__module__ = __name__

__all__ = ["fetch_eu_wob_ie"]
