"""Canonical wrapper for autotraveler.ru in Russian Federation."""

from fuel.fetchers._shared.eca.autotraveler import fetch_autotraveler_ru

fetch_autotraveler_ru.__module__ = __name__

__all__ = ["fetch_autotraveler_ru"]
