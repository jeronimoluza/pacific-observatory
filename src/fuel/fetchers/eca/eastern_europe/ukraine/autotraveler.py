"""Canonical wrapper for autotraveler.ru in Ukraine."""

from fuel.fetchers._shared.eca.autotraveler import fetch_autotraveler_ua

fetch_autotraveler_ua.__module__ = __name__

__all__ = ["fetch_autotraveler_ua"]
