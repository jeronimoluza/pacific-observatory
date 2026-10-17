"""Canonical wrapper for the EU Weekly Oil Bulletin in Netherlands."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_nl

fetch_eu_wob_nl.__module__ = __name__

__all__ = ["fetch_eu_wob_nl"]
