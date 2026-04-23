"""Canonical wrapper for autotraveler.ru in Armenia."""

from fuel.fetchers._shared.eca.autotraveler import fetch_autotraveler_am

fetch_autotraveler_am.__module__ = __name__

__all__ = ["fetch_autotraveler_am"]
