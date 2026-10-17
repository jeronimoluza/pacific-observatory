"""Canonical wrapper for the EU Weekly Oil Bulletin in Poland."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_pl

fetch_eu_wob_pl.__module__ = __name__

__all__ = ["fetch_eu_wob_pl"]
