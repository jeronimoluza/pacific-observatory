"""Canonical wrapper for the EU Weekly Oil Bulletin in Hungary."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_hu

fetch_eu_wob_hu.__module__ = __name__

__all__ = ["fetch_eu_wob_hu"]
