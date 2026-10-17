"""Canonical wrapper for the EU Weekly Oil Bulletin in Austria."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_at

fetch_eu_wob_at.__module__ = __name__

__all__ = ["fetch_eu_wob_at"]
