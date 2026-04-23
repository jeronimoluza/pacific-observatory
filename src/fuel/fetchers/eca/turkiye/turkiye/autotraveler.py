"""Canonical wrapper for autotraveler.ru in Türkiye."""

from fuel.fetchers._shared.eca.autotraveler import fetch_autotraveler_tr

fetch_autotraveler_tr.__module__ = __name__

__all__ = ["fetch_autotraveler_tr"]
