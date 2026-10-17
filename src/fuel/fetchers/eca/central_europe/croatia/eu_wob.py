"""Canonical wrapper for the EU Weekly Oil Bulletin in Croatia."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_hr

fetch_eu_wob_hr.__module__ = __name__

__all__ = ["fetch_eu_wob_hr"]
