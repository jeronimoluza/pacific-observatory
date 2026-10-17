"""Canonical wrapper for the EU Weekly Oil Bulletin in Estonia."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_ee

fetch_eu_wob_ee.__module__ = __name__

__all__ = ["fetch_eu_wob_ee"]
