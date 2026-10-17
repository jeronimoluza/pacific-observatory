"""Canonical wrapper for the EU Weekly Oil Bulletin in Portugal."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_pt

fetch_eu_wob_pt.__module__ = __name__

__all__ = ["fetch_eu_wob_pt"]
