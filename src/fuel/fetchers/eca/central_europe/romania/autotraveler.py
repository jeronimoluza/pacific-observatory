"""Canonical wrapper for autotraveler.ru in Romania."""

from fuel.fetchers._shared.eca.autotraveler import fetch_autotraveler_ro

fetch_autotraveler_ro.__module__ = __name__

__all__ = ["fetch_autotraveler_ro"]
