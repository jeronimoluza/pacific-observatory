"""Canonical wrapper for the EU Weekly Oil Bulletin in Latvia."""

from fuel.fetchers._shared.eca.eu_wob import fetch_eu_wob_lv

fetch_eu_wob_lv.__module__ = __name__

__all__ = ["fetch_eu_wob_lv"]
