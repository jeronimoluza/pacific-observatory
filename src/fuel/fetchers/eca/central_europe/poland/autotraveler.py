"""Canonical wrapper for autotraveler.ru in Poland."""

from fuel.fetchers._shared.eca.autotraveler import fetch_autotraveler_pl

fetch_autotraveler_pl.__module__ = __name__

__all__ = ["fetch_autotraveler_pl"]
